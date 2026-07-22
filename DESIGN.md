# AI 릴스 자동화 파이프라인 — 전체 설계 문서 (v3: Gemini 비주얼 통일 + 발행은 당분간 수동)

> 최종 수정: 2026-07-22
> 방향 전환: 손그림(Excalidraw)/힉스필드 방식 → Gemini(Nano Banana) 기반 벡터 카툰 스타일로 전면 교체
> 우선순위 변경: 메타 API 자동 발행은 당분간 보류, **영상 자동 생성 파이프라인 완성이 최우선**. 발행은 사람이 수동으로 진행.

---

## 0. 버전 히스토리 요약

| 버전 | 비주얼 스타일 | 발행 |
|---|---|---|
| v1 | 힉스필드 실사풍 AI 인간 캐릭터 | 메타 API 검토 중 |
| v2 | 손그림(Excalidraw) 다이어그램 + 흑백 스케치 마스코트 | 메타 API + 텔레그램 승인 |
| **v3 (현재)** | **Gemini(Nano Banana) 참조 이미지 기반 벡터 카툰 캐릭터 + 동일 스타일 아이콘/소품** | **당분간 수동 업로드**, 메타 API는 후순위 |

---

## 1. 프로젝트 개요

### 1.1 목표
- 중년 남성 캐릭터(안경, 콧수염, 니트+패딩 조끼 스타일)가 Claude/AI 팁을 설명하는 릴스 자동 생성
- 화면 상단에는 설명 주제에 맞는 아이콘/소품 세트가 표시되고, 캐릭터 표정도 상황에 맞춰 바뀜
- **영상 자동 생성까지의 파이프라인 완성이 1차 목표.** 메타 API 발행 자동화는 2차 목표로 미룸 (병목이 풀리기 전까지 수동 업로드로 충분)

### 1.2 2레이어 구조

| 레이어 | 역할 | 담당 |
|---|---|---|
| 두뇌 | 소재 리서치, 대본 작성, 이미지 생성 프롬프트 구성, 검토 요청 | Python 오케스트레이터 + Gemini API |
| 손발 | 캐릭터/아이콘 이미지 생성, 합성, (당분간) 수동 발행 안내 | Gemini API, ffmpeg, edge-tts |

---

## 2. 비주얼 시스템 (Gemini 기반)

### 2.1 캐릭터 — 참조 이미지 기반 일관성 유지

**베이스 캐릭터 프롬프트** (1회 생성, 이후 모든 장면의 기준 참조 이미지로 사용):
```
middle-aged Korean man, salt-and-pepper side-parted hair, glasses, mustache,
wearing a navy quilted puffer vest over a brown cable-knit sweater with white
collar shirt underneath, gray slacks, brown loafers, wristwatch, friendly warm
smile, flat vector cartoon illustration style, clean black outlines, soft flat
colors, white background, full body, front-facing, standing pose
```

**표정/포즈 변형 생성 방식**: 베이스 이미지를 참조 이미지로 첨부하고, 변경할 부분만 텍스트로 지시
```python
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-3-pro-image")  # 또는 gemini-2.5-flash-image (저비용)

base_image = genai.upload_file("assets/character/base.png")

response = model.generate_content([
    base_image,
    "Same character, same clothing and art style, exact same white background. "
    "Change only the facial expression to surprised — mouth open, eyebrows raised. "
    "Keep pose, body, and everything else identical."
])
```

- 필요한 표정/포즈 세트 (에피소드 전체에서 재사용):
  1. 기본(자연스러운 미소) 2. 놀람 3. 끄덕임/공감 4. 포인팅(가리키기) 5. 갸우뚱(의문) 6. 축하/신남
- 참조 이미지 방식이라 <cite index="39-1">최대 14장까지 참조 이미지를 한 번에 넣어 스타일 전송과 캐릭터 일관성을 유지할 수 있어서,</cite> 매번 새로 생성해도 옷·얼굴이 흔들리지 않음

### 2.2 상단 아이콘/소품 — 동일 스타일로 통일 생성
- 캐릭터와 같은 "flat vector cartoon, clean black outlines" 스타일 키워드를 프롬프트에 고정 포함
- 에피소드 주제에 맞는 소품 세트를 매번 새로 생성 (예: "키보드, 톱니바퀴, 로봇팔, 반짝이는 별" 등)
- 프롬프트 템플릿:
  ```
  flat vector cartoon illustration style, clean black outlines, soft flat colors,
  white background, no shadows: {episode_specific_objects}, arranged in a small
  grid, matching the art style of a friendly cartoon presenter character
  ```
- 생성된 소품 세트는 `assets/props/epXX/`에 저장, 영상 상단 영역에 합성

### 2.3 비용
- <cite index="39-1">Nano Banana 기준 이미지 1장당 약 $0.039.</cite> Nano Banana 2 Lite 등 더 저렴한 옵션도 있음
- 에피소드당: 캐릭터 표정 3~4장 + 소품 세트 1~2장 ≈ 5~6장 ≈ **$0.2~0.3 수준** (힉스필드 대비 매우 저렴)

---

## 3. 디렉토리 구조

```
reels-automation/
├── config/
│   ├── character.json         # 캐릭터 프롬프트, 표정/포즈 목록, 참조 이미지 경로
│   └── settings.json          # API 키 경로, 예산 상한
├── episodes/
│   └── epXX_제목.json          # 대본 + 표정 큐 + 소품 프롬프트 + 자막
├── assets/
│   ├── character/             # 베이스 + 표정별 캐릭터 PNG
│   ├── props/                 # 에피소드별 소품 아이콘 세트
│   ├── bgm/
│   └── fonts/
├── output/
│   ├── narration/              # edge-tts 생성 음성
│   ├── final/                  # 합성 완료된 최종 mp4
│   └── ready_to_publish/       # 검토 승인 완료, 수동 업로드 대기 폴더
├── scripts/
│   ├── 01_research.py          # 트렌드 리서치 (Gemini API + Google Search grounding)
│   ├── 02_script_gen.py        # 대본 + 표정 큐 + 소품 프롬프트 생성
│   ├── 03_generate_character.py # Gemini API — 참조 이미지 기반 표정/포즈 생성
│   ├── 04_generate_props.py    # Gemini API — 소품 세트 생성
│   ├── 05_narration.py         # edge-tts 나레이션
│   ├── 06_compose.py           # ffmpeg 합성 (캐릭터+소품 배치, 자막 번인, BGM 믹싱)
│   ├── 07_review_bot.py        # 텔레그램 검토/승인 봇
│   ├── 08_manual_publish_notice.py # 승인 완료 시 "업로드해주세요" 알림만 (자동 발행 아님)
│   └── pipeline.py             # 전체 오케스트레이터
├── logs/
│   └── run_log.csv
├── requirements.txt
└── README.md
```

---

## 4. 모듈별 설계

### 4.1 `01_research.py` — 트렌드 리서치
- Gemini API (`google-generativeai`) + Google Search grounding(`google_search_retrieval` 툴)으로 소재 후보 3~5개 수집
- Anthropic API는 사용하지 않음 — 리서치·대본 생성 포함 텍스트 작업 전부 Gemini로 통일
- **사람 개입 지점 ①**: 소재 선택

### 4.2 `02_script_gen.py` — 대본 + 큐 생성
- 후킹-문제-소개-포인트-CTA 구조 나레이션 스크립트
- 각 구간별 캐릭터 표정 큐 + 상단 소품 프롬프트 생성
- 출력 예:
  ```json
  {
    "title": "Superpowers 플러그인",
    "narration_script": "...",
    "captions": ["...", "..."],
    "expression_cues": [
      {"pose": "base", "start": 0, "duration": 3},
      {"pose": "pointing", "start": 3, "duration": 5},
      {"pose": "surprised", "start": 8, "duration": 4}
    ],
    "props_prompt": "keyboard, gear, robot arm, sparkles, replacing repetitive manual coding tasks"
  }
  ```

### 4.3 `03_generate_character.py` — 캐릭터 이미지 생성
- 베이스 이미지가 없으면 최초 1회 생성 → `assets/character/base.png` 저장
- 에피소드에서 필요한 표정이 `assets/character/{pose}.png`에 없으면 베이스 참조 + 프롬프트로 신규 생성, 있으면 재사용 (중복 생성 방지로 비용 절감)

### 4.4 `04_generate_props.py` — 소품 세트 생성
- 에피소드별 매번 새로 생성 (재사용성 낮음, 주제마다 다름)
- 스타일 키워드는 캐릭터와 동일하게 고정

### 4.5 `05_narration.py` — 나레이션 + 자막 동시 생성 (무료 TTS)
- edge-tts, `voice="ko-KR-InJoonNeural"` (중년 남성 톤에 맞는 보이스로 선택 — 실제 샘플 비교 필요)
- **핵심**: edge-tts의 `SubMaker`가 단어별 타임스탬프를 함께 뽑아주므로, 나레이션 음성과 정확히 싱크된 SRT 자막을 자동 생성 — 사람이 타이밍을 수동으로 맞출 필요 없음

```python
import edge_tts
import asyncio

async def generate_narration_with_captions(text, output_audio, output_srt, voice="ko-KR-InJoonNeural"):
    communicate = edge_tts.Communicate(text=text, voice=voice)
    submaker = edge_tts.SubMaker()

    with open(output_audio, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())
```
- 출력: `output/narration/epXX.mp3`, `output/narration/epXX.srt`

### 4.6 `06_compose.py` — ffmpeg 합성

**캔버스 레이아웃 (9:16, 1080×1920 기준)**
```
0    ~  640px  → 소품/아이콘 영역 (상단, 고정)
640  ~  900px  → 자막 영역 (중단, 고정 위치)
900  ~ 1920px  → 캐릭터 영역 (하단, 표정별 교체)
```

**합성 순서**
1. 흰색 배경 캔버스 생성
2. 소품 이미지를 상단에 overlay
3. `expression_cues`에 따라 캐릭터 이미지를 타이밍 구간별로 overlay 교체
4. `subtitles` 필터로 SRT 자막을 자막 영역에 번인 (drawtext로 한 줄씩 수동 지정하지 않음)
5. 나레이션 오디오 매핑 (BGM 믹싱 시 `amix`로 나레이션 1.5 : BGM 0.25~0.3)

**filter_complex 동적 생성 (표정 개수가 에피소드마다 달라지므로 코드로 조립)**
```python
def build_filter_complex(expression_cues, srt_path,
                          canvas_w=1080, canvas_h=1920,
                          props_h=600, char_w=700, char_y=950):
    filters = [
        f"[0:v]scale={canvas_w}:{props_h}[props]",
        f"color=white:s={canvas_w}x{canvas_h}:d=15[bg]",
        "[bg][props]overlay=0:0[bg1]",
    ]
    prev = "bg1"
    char_x = (canvas_w - char_w) // 2
    for i, cue in enumerate(expression_cues):
        input_idx = i + 2  # 0=props, 1=narration audio 다음부터 캐릭터 이미지 인덱스
        label = f"bg{i + 2}"
        filters.append(f"[{input_idx}:v]scale={char_w}:-1[char{i}]")
        filters.append(
            f"[{prev}][char{i}]overlay={char_x}:{char_y}:"
            f"enable='between(t,{cue['start']},{cue['start'] + cue['duration']})'[{label}]"
        )
        prev = label
    filters.append(
        f"[{prev}]subtitles={srt_path}:force_style="
        f"'FontName=NanumSquareRound,FontSize=42,Alignment=2,MarginV=850'[v]"
    )
    return ";".join(filters)
```

**실행 예시 (ffmpeg 호출부)**
```python
import subprocess

def compose_episode(props_path, character_images, expression_cues,
                     narration_path, srt_path, bgm_path, output_path):
    filter_complex = build_filter_complex(expression_cues, srt_path)

    inputs = ["-loop", "1", "-i", props_path]
    for img in character_images:
        inputs += ["-loop", "1", "-i", img]
    inputs += ["-i", narration_path, "-i", bgm_path]

    audio_filter = (
        f"[{len(character_images)+1}:a]volume=1.5[narr];"
        f"[{len(character_images)+2}:a]volume=0.28[bgm];"
        f"[narr][bgm]amix=inputs=2:duration=first[a]"
    )

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", f"{filter_complex};{audio_filter}",
        "-map", "[v]", "-map", "[a]",
        "-shortest", output_path,
    ]
    subprocess.run(cmd, check=True)
```

- 출력: `output/final/epXX_final.mp4`
- **참고**: 표정이 바뀔 때 자연스러운 전환이 필요하면 `overlay` 대신 각 구간 경계에 `fade`를 살짝 추가하거나, crossfade 0.2~0.3초를 넣어 딱딱 끊기지 않게 조정 가능

### 4.7 `07_review_bot.py` — 텔레그램 검토
- 최종 mp4 + 캡션 초안을 텔레그램으로 전송, ✅승인 / ✏️수정 / ❌반려 버튼
- ✅ 승인 시 → 파일을 `output/ready_to_publish/`로 이동 + "업로드 대기 중" 알림

### 4.8 `08_manual_publish_notice.py` — 수동 발행 안내 (당분간)
- 메타 API 자동 발행 대신, 승인된 영상이 쌓이면 텔레그램으로 "이번 주 업로드할 N개 영상이 준비됐어요" 알림만 전송
- 실제 업로드는 사람이 인스타 앱에서 직접 진행
- **추후 메타 앱 심사가 완료되면 이 모듈을 `08_meta_publish.py`로 교체 예정** (설계는 그대로 두되 지금 우선순위 아님)

### 4.9 `pipeline.py`
```
python pipeline.py --step research
python pipeline.py --step script --episode ep01
python pipeline.py --step character --episode ep01
python pipeline.py --step props --episode ep01
python pipeline.py --step narrate --episode ep01
python pipeline.py --step compose --episode ep01
python pipeline.py --step review --episode ep01   # 텔레그램 승인 → ready_to_publish로 이동
python pipeline.py --step all --episode ep01
```

---

## 5. 실행 환경

- Python 3.11+
- `requirements.txt` 핵심: `requests`, `python-dotenv`, `google-generativeai`, `edge-tts`, `python-telegram-bot`, `ffmpeg-python`(선택)
- Anthropic API는 사용하지 않음 (텍스트/리서치 작업 포함 전부 Gemini API로 통일)
- ffmpeg 로컬 설치 필수 (**`subtitles` 필터를 쓰려면 `libass` 포함 빌드여야 함** — `ffmpeg -filters | grep subtitles`로 확인)
- Gemini API 키 (`GEMINI_API_KEY`) 발급 필요
- 실행 위치: 로컬

---

## 6. 비용 구조 요약

| 항목 | 비용 |
|---|---|
| 캐릭터 표정 이미지 | 최초 1세트 생성 후 재사용 → 사실상 반복 비용 거의 없음 |
| 에피소드별 소품 세트 | 장당 약 $0.039 × 5~6장 ≈ $0.2~0.3 |
| 나레이션 | 무료 (edge-tts) |
| 발행 | 무료 (수동 업로드) |
| **에피소드당 총비용** | **약 $0.2~0.3 수준** |

---

## 7. TODO / 다음 단계 (우선순위 순)

- [ ] **1순위 — 캐릭터 베이스 이미지 실제 생성** (Gemini API 키 발급 후)
- [ ] 표정 5~6종 참조 이미지 방식으로 생성 테스트 (일관성 확인)
- [ ] 에피소드 1개 분량 소품 세트 생성 테스트
- [ ] edge-tts 한국어 남성 보이스 샘플 비교 및 선정
- [ ] `06_compose.py` ffmpeg 합성 스크립트 프로토타입 (`build_filter_complex` 함수 실제 동작 검증, `subtitles` 필터 폰트 렌더링 확인)
- [ ] 텔레그램 봇 생성(@BotFather) 및 토큰 발급
- [ ] EP.1 (Superpowers) 엔드투엔드 테스트 (리서치 → 텔레그램 승인 → ready_to_publish 폴더 확인까지)
- [ ] 인스타 프로필/캡션에 AI 생성 콘텐츠 고지 문구 확정
- [ ] (후순위, 병목 해소 후) 인스타 비즈니스 계정 전환 + 메타 앱 심사 + `08_meta_publish.py` 구현

---

## 8. 확정된 결정사항 요약

| 항목 | 결정 |
|---|---|
| 실행 환경 | 로컬 |
| 스크립트 언어 | Python |
| 비주얼 스타일 | Gemini(Nano Banana) 참조 이미지 기반 벡터 카툰 캐릭터 |
| 캐릭터 컨셉 | 중년 남성, 안경/콧수염, 니트+패딩 조끼, 친근한 인상 |
| 상단 아이콘/소품 | 캐릭터와 동일 스타일로 Gemini 생성, 에피소드마다 신규 생성 |
| 나레이션 | edge-tts (무료) + SubMaker로 자막 자동 싱크 |
| 발행 방식 | **당분간 수동 업로드** (사람이 직접 진행) — 메타 API 자동 발행은 후순위 |
| 사람 개입 지점 | ① 소재 선택 ② 텔레그램 최종 승인 ③ (임시) 수동 업로드 |
| 우선순위 | 영상 자동 생성 파이프라인 완성 > 발행 자동화 |

## 9. 에피소드 소재 목록 + 후킹 강화 대본

### 9.1 후킹 강화 기법 참고표

| 기법 | 약한 버전 | 강화 버전 |
|---|---|---|
| 숫자 충격 | "다들 이거 몰라요" | "깃허브 스타 7만 9천 개, 근데 아직도 모르는 사람 많더라고요" |
| 부정 프레이밍 | "이거 알려드릴게요" | "이거 모르고 Claude 쓰면 절반만 쓰는 거예요" |
| 궁금증 갭 | "이런 기능이 있어요" | "AI가 스스로 스킬을 만든다고요? 이거 실화예요" |
| 대조/반전 | "설명드릴게요" | "다들 어렵다는데, 사실 명령어 한 줄이면 끝나요" |
| 즉시 행동 유도 | "저장하세요" | "지금 안 보면 다음 주에 또 검색하게 될걸요" |

모든 에피소드 대본의 후킹 구간(0~2초)은 이 표의 기법 중 하나 이상을 적용해서 작성한다.

### 9.2 에피소드 목록 (EP.1~6은 기존, EP.7~8은 최신 트렌드 반영 추가)

| EP | 소재 | 비고 |
|---|---|---|
| 1 | Superpowers 플러그인 | 스타 약 7만 9천 개로 최신화 |
| 2 | Skills vs MCP 차이 | |
| 3 | Skills 마켓플레이스 | |
| 4 | Skills의 진짜 한계 | |
| 5 | Playwright Skill | |
| 6 | 대화 기억 스킬 | |
| 7 | hermes-agent (자기개선형 에이전트) | 스타 약 5,700개, 신규 |
| 8 | page-agent (자연어 화면 제어) | 스타 약 5,400개, 신규 |

### 9.3 신규 에피소드 대본

**EP.7 — hermes-agent**
> (후킹) "AI가 대화하면서 스스로 스킬을 만든다고요? 이거 실화예요."
> (문제) "매번 같은 실수 반복하는 AI, 지치지 않으세요?"
> (소개) "hermes-agent는 경험에서 스스로 배우는 에이전트예요."
> (포인트1) "대화 패턴을 발견하면 자동으로 '스킬'을 만들어서 저장해요."
> (포인트2) "다음에 비슷한 상황 오면 그 스킬을 알아서 꺼내 써요."
> (포인트3) "텔레그램·디스코드·슬랙 연동에 스케줄러까지 있어서 무인 자동화도 가능해요."
> (CTA) "이거 하나로 AI가 진짜 '경험'을 쌓기 시작해요. 저장하세요."

**EP.8 — page-agent**
> (후킹) "마우스 클릭 없이, 말로만 웹사이트 조작하는 거 봤어요?"
> (문제) "반복 작업 매크로 짜는 거, 매번 귀찮으셨죠?"
> (소개) "page-agent는 자연어 명령으로 웹 화면을 직접 제어해요."
> (포인트1) "'로그인하고 주문 내역 확인해줘' 한마디면 끝나요."
> (포인트2) "코드 한 줄 안 짜고 화면 자체를 이해해서 조작해요."
> (포인트3) "스타 5천 개 넘게 받은 신생 프로젝트라 지금 써보면 얼리어답터예요."
> (CTA) "이거 다음 주에 또 검색하지 말고 지금 저장하세요."

---

## 10. 발행 관련 재확인 — 지금은 사람이 직접 업로드

- 메타 Graph API 발급/앱 심사 전까지, **완성된 영상 업로드는 사용자가 직접 인스타 앱에서 수행**한다.
- 파이프라인은 `output/ready_to_publish/`에 승인된 영상을 쌓아두는 것까지만 자동화하고, 그 이후 실제 업로드 버튼을 누르는 행위는 사람의 몫이다.
- `08_manual_publish_notice.py`가 텔레그램으로 "업로드 대기 중인 영상 N개" 알림만 보내고, 실제 발행 API 호출은 하지 않는다.
- 메타 앱 심사가 완료되는 시점에 `08_meta_publish.py`로 교체해 이 단계까지 자동화할 수 있다 (섹션 4.8 참고).
