# 릴스 자동화 파이프라인 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DESIGN.md v3에 정의된 인스타 릴스 자동 생성 파이프라인(캐릭터/소품 이미지 생성 → 나레이션 → ffmpeg 합성 → 텔레그램 검토 → 수동 발행 대기)을 실제로 동작하는 코드로 구현하고, 사용 가능한 API 키(GEMINI_API_KEY, TELEGRAM_BOT_TOKEN)로 실제 실행까지 검증한다.

**Architecture:** Python 3.12 venv 기반 스크립트 모음(01~08) + `pipeline.py` 오케스트레이터. 텍스트/이미지 생성은 전부 Gemini API(`google-genai` SDK, Interactions API)로 통일하고 Anthropic API는 사용하지 않는다. 나레이션은 edge-tts, 합성은 ffmpeg, 검토는 텔레그램 봇.

**Tech Stack:** Python 3.12, `google-genai`(Gemini, Interactions API), `edge-tts`, `python-telegram-bot` v22 (asyncio), `ffmpeg`(libass 포함), `pytest`.

## Global Constraints

- Anthropic/Claude API 사용 금지 — 리서치·대본 생성 포함 모든 텍스트 작업은 Gemini API로 통일 (DESIGN.md, CLAUDE.md 이미 수정됨)
- 발행은 당분간 수동 — `output/ready_to_publish/`에 쌓는 것까지만 자동화, 실제 업로드는 사람이 인스타 앱에서 수행
- 모듈 번호(01~08) 순서와 DESIGN.md 섹션 3 디렉토리 구조를 그대로 따를 것
- API 키는 `.env`에서 `python-dotenv`로 로드 (이미 `/Users/cheonhyeonjun/insta_auto/.env`에 GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 존재)
- 캐릭터 표정 이미지는 파일이 이미 존재하면 재생성하지 않음 (비용 절감, DESIGN.md 4.3)
- Gemini 텍스트 모델: `gemini-3.6-flash` (Interactions API, 필요 시 `tools=[{"type": "google_search"}]`)
- Gemini 이미지 모델: `gemini-3.1-flash-image` (Interactions API, 참조 이미지 최대 14장 지원)
- 이 두 모델명은 2026-07-22 기준 공식 문서(ai.google.dev)에서 직접 확인한 값. 실행 시점에 모델 404가 나면 `ai.google.dev/gemini-api/docs/models` 최신 목록을 다시 확인할 것

## 검증된 Gemini SDK 사용법 (google-genai, Interactions API)

```python
from google import genai

client = genai.Client(api_key=GEMINI_API_KEY)

# 텍스트 (+ 검색 그라운딩)
interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input="...",
    tools=[{"type": "google_search"}],  # 검색 불필요하면 생략
)
print(interaction.output_text)

# 이미지 생성 (텍스트만, 또는 참조 이미지 + 텍스트)
import base64
input_parts = [{"type": "text", "text": "..."}]
# 참조 이미지가 있으면 추가:
input_parts.append({
    "type": "image",
    "data": base64.b64encode(image_bytes).decode("utf-8"),
    "mime_type": "image/png",
})
interaction = client.interactions.create(model="gemini-3.1-flash-image", input=input_parts)
with open(out_path, "wb") as f:
    f.write(base64.b64decode(interaction.output_image.data))
```

---

### Task 0: 프로젝트 스캐폴딩

**Files:**
- Create: `requirements.txt`
- Create: `config/character.json`
- Create: `config/settings.json`
- Create: `.gitignore`
- Create directories: `episodes/`, `assets/character/`, `assets/props/`, `assets/bgm/`, `assets/fonts/`, `output/narration/`, `output/final/`, `output/ready_to_publish/`, `scripts/`, `logs/`, `tests/`

**Interfaces:**
- Produces: `config/character.json`의 `poses` dict (키: `base`, `surprised`, `nodding`, `pointing`, `questioning`, `celebrating`) — Task 1, 2가 이 키를 사용
- Produces: `config/settings.json`의 `gemini_model_text`, `gemini_model_image`, `tts_voice`, `budget_limit_usd` — 이후 모든 스크립트가 참조

- [ ] **Step 1: 디렉토리 생성**

```bash
cd /Users/cheonhyeonjun/insta_auto
mkdir -p episodes assets/character assets/props assets/bgm assets/fonts \
  output/narration output/final output/ready_to_publish scripts logs tests
```

- [ ] **Step 2: Homebrew ffmpeg 설치 (libass 포함 여부 확인)**

```bash
brew install ffmpeg
ffmpeg -filters | grep subtitles
```
Expected: `subtitles` 필터가 목록에 출력됨 (libass 빌드 확인)

- [ ] **Step 3: Python 3.12 venv 생성**

```bash
/opt/homebrew/bin/python3.12 -m venv /Users/cheonhyeonjun/insta_auto/venv
```

- [ ] **Step 4: requirements.txt 작성**

```
python-dotenv
google-genai
edge-tts
python-telegram-bot==22.*
pytest
```

- [ ] **Step 5: 패키지 설치**

```bash
/Users/cheonhyeonjun/insta_auto/venv/bin/pip install -r /Users/cheonhyeonjun/insta_auto/requirements.txt
```

- [ ] **Step 6: config/character.json 작성**

```json
{
  "base_prompt": "middle-aged Korean man, salt-and-pepper side-parted hair, glasses, mustache, wearing a navy quilted puffer vest over a brown cable-knit sweater with white collar shirt underneath, gray slacks, brown loafers, wristwatch, friendly warm smile, flat vector cartoon illustration style, clean black outlines, soft flat colors, white background, full body, front-facing, standing pose",
  "reference_image": "assets/character/base.png",
  "poses": {
    "base": "Natural friendly smile, standing pose, front-facing. This is the base reference image itself.",
    "surprised": "Same character, same clothing and art style, exact same white background. Change only the facial expression to surprised — mouth open, eyebrows raised. Keep pose, body, and everything else identical.",
    "nodding": "Same character, same clothing and art style, exact same white background. Change only the pose to nodding in agreement, head tilted slightly down, warm understanding expression. Keep clothing, face, and everything else identical.",
    "pointing": "Same character, same clothing and art style, exact same white background. Change only the pose to pointing with one hand toward the viewer/upper area, confident expression. Keep clothing, face, and everything else identical.",
    "questioning": "Same character, same clothing and art style, exact same white background. Change only the pose to head tilted to one side with a curious/questioning expression, one eyebrow raised. Keep clothing and everything else identical.",
    "celebrating": "Same character, same clothing and art style, exact same white background. Change only the pose to both arms raised in celebration, big excited smile. Keep clothing and everything else identical."
  }
}
```

- [ ] **Step 7: config/settings.json 작성**

```json
{
  "gemini_model_text": "gemini-3.6-flash",
  "gemini_model_image": "gemini-3.1-flash-image",
  "tts_voice": "ko-KR-InJoonNeural",
  "budget_limit_usd": 5.0
}
```

- [ ] **Step 8: .gitignore 작성**

```
venv/
.env
__pycache__/
*.pyc
output/
.DS_Store
```

- [ ] **Step 9: git init + 첫 커밋**

```bash
cd /Users/cheonhyeonjun/insta_auto
git init
git add CLAUDE.md DESIGN.md requirements.txt config .gitignore
git commit -m "chore: scaffold reels pipeline project structure"
```

---

### Task 1: 캐릭터 베이스 이미지 생성 — `03_generate_character.py` (base)

**Files:**
- Create: `scripts/03_generate_character.py`

**Interfaces:**
- Consumes: `config/character.json`(`base_prompt`, `poses`), `config/settings.json`(`gemini_model_image`), `.env`(`GEMINI_API_KEY`)
- Produces: `assets/character/{pose}.png`; 함수 `generate_pose(pose_key: str, client, cfg, settings) -> pathlib.Path` — Task 2가 동일 함수를 반복 호출

- [ ] **Step 1: 스크립트 작성**

```python
# scripts/03_generate_character.py
import argparse
import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def generate_pose(pose_key: str, client: genai.Client, cfg: dict, settings: dict) -> Path:
    out_path = ROOT / "assets" / "character" / f"{pose_key}.png"
    if out_path.exists():
        print(f"[skip] {out_path} already exists")
        return out_path

    model = settings["gemini_model_image"]
    if pose_key == "base":
        input_parts = [{"type": "text", "text": cfg["base_prompt"]}]
    else:
        base_path = ROOT / cfg["reference_image"]
        if not base_path.exists():
            raise FileNotFoundError(f"base reference image missing: {base_path}. Generate 'base' pose first.")
        image_bytes = base_path.read_bytes()
        input_parts = [
            {"type": "text", "text": cfg["poses"][pose_key]},
            {"type": "image", "data": base64.b64encode(image_bytes).decode("utf-8"), "mime_type": "image/png"},
        ]

    interaction = client.interactions.create(model=model, input=input_parts)
    image_b64 = interaction.output_image.data
    out_path.write_bytes(base64.b64decode(image_b64))
    print(f"[ok] wrote {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pose", default="base", help="pose key from config/character.json, or 'all'")
    args = parser.parse_args()

    cfg = load_json(ROOT / "config" / "character.json")
    settings = load_json(ROOT / "config" / "settings.json")
    client = get_client()

    if args.pose == "all":
        for pose_key in cfg["poses"]:
            generate_pose(pose_key, client, cfg, settings)
    else:
        generate_pose(args.pose, client, cfg, settings)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실제 실행 — 베이스 이미지 생성 (Gemini API 실비용 발생, 약 $0.04)**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/python scripts/03_generate_character.py --pose base
```
Expected: `[ok] wrote .../assets/character/base.png` 출력, 파일 실제 생성

- [ ] **Step 3: 결과 확인**

```bash
file assets/character/base.png
```
Expected: PNG image data, 사람이 직접 열어서 캐릭터 컨셉(안경/콧수염/니트+패딩조끼)과 일치하는지 육안 확인 필요 — 이 단계는 사람 판단이 필요하므로 결과 이미지를 사용자에게 보고

- [ ] **Step 4: 커밋**

```bash
git add scripts/03_generate_character.py assets/character/base.png
git commit -m "feat: generate character base image via Gemini"
```

---

### Task 2: 표정 5종 생성 테스트

**Files:**
- Modify: 없음 (Task 1의 `generate_pose` 재사용)

**Interfaces:**
- Consumes: Task 1의 `generate_pose(pose_key, client, cfg, settings)`
- Produces: `assets/character/{surprised,nodding,pointing,questioning,celebrating}.png`

- [ ] **Step 1: 5종 표정 순차 생성 (실비용 약 $0.04 × 5 ≈ $0.2)**

```bash
cd /Users/cheonhyeonjun/insta_auto
for pose in surprised nodding pointing questioning celebrating; do
  venv/bin/python scripts/03_generate_character.py --pose "$pose"
done
```
Expected: 5개 파일 모두 `[ok] wrote ...` 출력

- [ ] **Step 2: 일관성 확인**

```bash
ls -la assets/character/
```
Expected: base.png 포함 6개 PNG 파일. 사용자에게 이미지들을 보여주고 캐릭터 일관성(같은 옷, 같은 얼굴) 육안 확인 요청

- [ ] **Step 3: 커밋**

```bash
git add assets/character/
git commit -m "feat: generate 5 character expression variants"
```

---

### Task 3: 소품 세트 생성 테스트 (EP.1) — `04_generate_props.py`

**Files:**
- Create: `scripts/04_generate_props.py`
- Create: `episodes/ep01_superpowers.json` (임시 fixture — Task 7에서 `02_script_gen.py`가 전체 내용으로 덮어씀)

**Interfaces:**
- Consumes: `episodes/{episode_id}.json`(`props_prompt`), `config/settings.json`(`gemini_model_image`)
- Produces: `assets/props/{episode_id}/props.png`; 함수 `generate_props(episode_id, props_prompt, client, settings) -> pathlib.Path` — Task 7의 pipeline.py가 재사용

- [ ] **Step 1: EP.1 임시 fixture 작성**

```json
{
  "title": "Superpowers 플러그인",
  "props_prompt": "flat vector cartoon illustration style, clean black outlines, soft flat colors, white background, no shadows: keyboard, magic wand with sparkles, glowing plugin puzzle piece, gear, lightning bolt, arranged in a small grid, matching the art style of a friendly cartoon presenter character"
}
```
저장: `episodes/ep01_superpowers.json`

- [ ] **Step 2: 스크립트 작성**

```python
# scripts/04_generate_props.py
import argparse
import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def generate_props(episode_id: str, props_prompt: str, client: genai.Client, settings: dict) -> Path:
    out_dir = ROOT / "assets" / "props" / episode_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "props.png"

    interaction = client.interactions.create(
        model=settings["gemini_model_image"],
        input=[{"type": "text", "text": props_prompt}],
    )
    out_path.write_bytes(base64.b64decode(interaction.output_image.data))
    print(f"[ok] wrote {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", required=True, help="episode id, e.g. ep01_superpowers")
    args = parser.parse_args()

    episode = load_json(ROOT / "episodes" / f"{args.episode}.json")
    settings = load_json(ROOT / "config" / "settings.json")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    generate_props(args.episode, episode["props_prompt"], client, settings)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 실제 실행 (실비용 약 $0.04)**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/python scripts/04_generate_props.py --episode ep01_superpowers
```
Expected: `assets/props/ep01_superpowers/props.png` 생성

- [ ] **Step 4: 커밋**

```bash
git add scripts/04_generate_props.py episodes/ep01_superpowers.json assets/props/
git commit -m "feat: generate EP.1 props set via Gemini"
```

---

### Task 4: edge-tts 보이스 비교 및 선정 — `05_narration.py`

**Files:**
- Create: `scripts/05_narration.py`
- Modify: `config/settings.json` (`tts_voice` 확정값 반영)

**Interfaces:**
- Produces: 함수 `generate_narration_with_captions(text, output_audio, output_srt, voice) -> None` — Task 5, Task 7이 재사용

- [ ] **Step 1: 사용 가능한 한국어 남성 보이스 목록 실제 조회**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/edge-tts --list-voices | grep "ko-KR" | grep -i male
```
Expected: `ko-KR-InJoonNeural` 포함 한국어 남성 보이스 목록 출력 — 이 결과로 아래 VOICE_CANDIDATES 실제 값 확정

- [ ] **Step 2: 스크립트 작성**

```python
# scripts/05_narration.py
import argparse
import asyncio
import json
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent.parent

SAMPLE_TEXT = "깃허브 스타 7만 9천 개, 근데 아직도 모르는 사람 많더라고요. 이거 모르고 Claude 쓰면 절반만 쓰는 거예요."


async def generate_narration_with_captions(text: str, output_audio: Path, output_srt: Path, voice: str) -> None:
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


async def compare_voices(voices: list[str]) -> None:
    out_dir = ROOT / "output" / "narration"
    out_dir.mkdir(parents=True, exist_ok=True)
    for voice in voices:
        audio_path = out_dir / f"voice_test_{voice}.mp3"
        srt_path = out_dir / f"voice_test_{voice}.srt"
        await generate_narration_with_captions(SAMPLE_TEXT, audio_path, srt_path, voice)
        print(f"[ok] {voice} -> {audio_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", nargs="+", help="voice names to compare")
    parser.add_argument("--text", help="narration text")
    parser.add_argument("--out-audio")
    parser.add_argument("--out-srt")
    parser.add_argument("--voice")
    args = parser.parse_args()

    if args.compare:
        asyncio.run(compare_voices(args.compare))
    else:
        settings = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
        voice = args.voice or settings["tts_voice"]
        asyncio.run(generate_narration_with_captions(args.text, Path(args.out_audio), Path(args.out_srt), voice))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Step 1에서 확인한 실제 한국어 남성 보이스들로 비교 샘플 생성 (무료)**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/python scripts/05_narration.py --compare ko-KR-InJoonNeural ko-KR-HyunsuMultilingualNeural
```
(Step 1 결과에 따라 실제 존재하는 보이스명으로 인자 조정)

- [ ] **Step 4: 사용자에게 mp3 샘플 전달 후 최종 보이스 선택받아 `config/settings.json`의 `tts_voice` 확정**

- [ ] **Step 5: 커밋**

```bash
git add scripts/05_narration.py config/settings.json
git commit -m "feat: add edge-tts narration module, finalize voice selection"
```

---

### Task 5: ffmpeg 합성 프로토타입 — `06_compose.py`

**Files:**
- Create: `scripts/06_compose.py`
- Create: `tests/test_compose.py`

**Interfaces:**
- Consumes: `assets/character/{pose}.png`, `assets/props/{episode_id}/props.png`, narration `.mp3`/`.srt` (Task 4)
- Produces: `output/final/{episode_id}_final.mp4`; 함수 `build_filter_complex(expression_cues, srt_path, ...) -> str`, `compose_episode(...) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_compose.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from importlib import import_module

compose = import_module("06_compose")


def test_build_filter_complex_basic_structure():
    cues = [
        {"pose": "base", "start": 0, "duration": 3},
        {"pose": "pointing", "start": 3, "duration": 5},
    ]
    result = compose.build_filter_complex(cues, "output/narration/ep01.srt")

    assert "[0:v]scale=1080:600[props]" in result
    assert "color=white:s=1080x1920:d=15[bg]" in result
    assert result.count("overlay=") == 3  # props overlay + 2 char overlays
    assert "subtitles=output/narration/ep01.srt" in result
    assert result.endswith("[v]")


def test_build_filter_complex_empty_cues():
    result = compose.build_filter_complex([], "output/narration/ep01.srt")
    assert "subtitles=" in result
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/pytest tests/test_compose.py -v
```
Expected: FAIL (`06_compose` 모듈 없음)

- [ ] **Step 3: `build_filter_complex` 구현**

```python
# scripts/06_compose.py
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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
        input_idx = i + 2
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


def compose_episode(props_path, character_images, expression_cues,
                     narration_path, srt_path, bgm_path, output_path):
    filter_complex = build_filter_complex(expression_cues, srt_path)

    inputs = ["-loop", "1", "-i", str(props_path)]
    for img in character_images:
        inputs += ["-loop", "1", "-i", str(img)]
    inputs += ["-i", str(narration_path), "-i", str(bgm_path)]

    audio_filter = (
        f"[{len(character_images)+1}:a]volume=1.5[narr];"
        f"[{len(character_images)+2}:a]volume=0.28[bgm];"
        f"[narr][bgm]amix=inputs=2:duration=first[a]"
    )

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", f"{filter_complex};{audio_filter}",
        "-map", "[v]", "-map", "[a]",
        "-shortest", str(output_path),
    ]
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", required=True)
    args = parser.parse_args()

    episode = json.loads((ROOT / "episodes" / f"{args.episode}.json").read_text(encoding="utf-8"))
    props_path = ROOT / "assets" / "props" / args.episode / "props.png"
    character_images = [ROOT / "assets" / "character" / f"{c['pose']}.png" for c in episode["expression_cues"]]
    narration_path = ROOT / "output" / "narration" / f"{args.episode}.mp3"
    srt_path = ROOT / "output" / "narration" / f"{args.episode}.srt"
    bgm_path = ROOT / "assets" / "bgm" / "default.mp3"
    output_path = ROOT / "output" / "final" / f"{args.episode}_final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    compose_episode(props_path, character_images, episode["expression_cues"],
                     narration_path, srt_path, bgm_path, output_path)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 재실행 — 통과 확인**

```bash
venv/bin/pytest tests/test_compose.py -v
```
Expected: PASS

- [ ] **Step 5: BGM 플레이스홀더 준비 (무음 트랙, 저작권 문제 없는 실제 BGM은 후속 과제로 별도 확보)**

```bash
ffmpeg -f lavfi -i anullsrc=r=44100:cl=stereo -t 15 -q:a 9 -acodec libmp3lame assets/bgm/default.mp3
```

- [ ] **Step 6: EP.1 나레이션 실제 생성 (Task 4의 최종 확정 보이스 사용)**

```bash
venv/bin/python -c "
import asyncio, sys
sys.path.insert(0, 'scripts')
from importlib import import_module
narration = import_module('05_narration')
asyncio.run(narration.generate_narration_with_captions(
    '깃허브 스타 7만 9천 개, 근데 아직도 모르는 사람 많더라고요. 이거 모르고 Claude 쓰면 절반만 쓰는 거예요. Superpowers 플러그인을 소개합니다.',
    'output/narration/ep01_superpowers.mp3',
    'output/narration/ep01_superpowers.srt',
    'ko-KR-InJoonNeural'))
"
```

- [ ] **Step 7: `episodes/ep01_superpowers.json`에 최소 `expression_cues` 추가**

```json
{
  "title": "Superpowers 플러그인",
  "props_prompt": "flat vector cartoon illustration style, clean black outlines, soft flat colors, white background, no shadows: keyboard, magic wand with sparkles, glowing plugin puzzle piece, gear, lightning bolt, arranged in a small grid, matching the art style of a friendly cartoon presenter character",
  "expression_cues": [
    {"pose": "base", "start": 0, "duration": 5},
    {"pose": "pointing", "start": 5, "duration": 5}
  ]
}
```

- [ ] **Step 8: 실제 ffmpeg 합성 실행**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/python scripts/06_compose.py --episode ep01_superpowers
```
Expected: `output/final/ep01_superpowers_final.mp4` 생성. `ffplay` 또는 Finder에서 열어 자막 폰트 렌더링 확인 — `NanumSquareRound` 폰트가 시스템에 없으면 자막이 기본 폰트로 대체되거나 비어 보일 수 있음. 이 경우 `assets/fonts/`에 폰트 파일을 넣고 `force_style`에 `fontsdir=assets/fonts` 옵션 추가 필요 (후속 조정)

- [ ] **Step 9: 커밋**

```bash
git add scripts/06_compose.py tests/test_compose.py assets/bgm/ episodes/ep01_superpowers.json
git commit -m "feat: add ffmpeg compose module with tested build_filter_complex"
```

---

### Task 6: 텔레그램 검토 봇 — `07_review_bot.py`

**Files:**
- Create: `scripts/07_review_bot.py`

**Interfaces:**
- Consumes: `.env`(`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), `output/final/{episode_id}_final.mp4`
- Produces: 승인 시 `output/ready_to_publish/{episode_id}_final.mp4`로 이동; 함수 `send_for_review(episode_id, video_path, caption) -> None`

- [ ] **Step 1: 스크립트 작성**

```python
# scripts/07_review_bot.py
import argparse
import asyncio
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

APPROVE, EDIT, REJECT = "approve", "edit", "reject"


def build_keyboard(episode_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 승인", callback_data=f"{APPROVE}:{episode_id}"),
        InlineKeyboardButton("✏️ 수정", callback_data=f"{EDIT}:{episode_id}"),
        InlineKeyboardButton("❌ 반려", callback_data=f"{REJECT}:{episode_id}"),
    ]])


async def send_for_review(episode_id: str, video_path: Path, caption: str) -> None:
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    with open(video_path, "rb") as f:
        await bot.send_video(chat_id=chat_id, video=f, caption=caption, reply_markup=build_keyboard(episode_id))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, episode_id = query.data.split(":", 1)

    if action == APPROVE:
        src = ROOT / "output" / "final" / f"{episode_id}_final.mp4"
        dst_dir = ROOT / "output" / "ready_to_publish"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        shutil.move(str(src), str(dst))
        await query.edit_message_caption(caption=f"✅ 승인됨 — {dst} 로 이동, 업로드 대기 중")
    elif action == EDIT:
        await query.edit_message_caption(caption="✏️ 수정 요청됨 — 대본/이미지 재검토 필요")
    else:
        await query.edit_message_caption(caption="❌ 반려됨")


async def run_bot_for(seconds: int) -> None:
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CallbackQueryHandler(on_callback))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.sleep(seconds)
    await app.updater.stop()
    await app.stop()
    await app.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", required=True)
    parser.add_argument("--caption", default="검토 요청")
    parser.add_argument("--listen-seconds", type=int, default=300)
    args = parser.parse_args()

    video_path = ROOT / "output" / "final" / f"{args.episode}_final.mp4"

    async def flow():
        await send_for_review(args.episode, video_path, args.caption)
        await run_bot_for(args.listen_seconds)

    asyncio.run(flow())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실제 연결 테스트 — 텍스트 메시지만 우선 전송 (무료, 연결 확인용)**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/python -c "
import asyncio, os
from dotenv import load_dotenv
from telegram import Bot
load_dotenv('.env')
async def main():
    bot = Bot(token=os.environ['TELEGRAM_BOT_TOKEN'])
    await bot.send_message(chat_id=os.environ['TELEGRAM_CHAT_ID'], text='reels-automation 봇 연결 테스트')
asyncio.run(main())
"
```
Expected: 사용자 텔레그램에 메시지 도착 확인 (사용자 확인 필요)

- [ ] **Step 3: EP.1 영상으로 실제 검토 요청 실행 — 사용자가 5분 내 버튼 클릭**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/python scripts/07_review_bot.py --episode ep01_superpowers --caption "EP.1 Superpowers 플러그인 검토 요청" --listen-seconds 300
```
사용자에게: 텔레그램에서 영상 확인 후 ✅ 승인 버튼을 눌러달라고 요청. 승인 시 `output/ready_to_publish/ep01_superpowers_final.mp4` 생성 확인

- [ ] **Step 4: 커밋**

```bash
git add scripts/07_review_bot.py
git commit -m "feat: add telegram review bot with approve/edit/reject flow"
```

---

### Task 7: 리서치 + 대본생성 + 파이프라인 + EP.1 엔드투엔드 — `01_research.py`, `02_script_gen.py`, `pipeline.py`, `08_manual_publish_notice.py`

**Files:**
- Create: `scripts/01_research.py`
- Create: `scripts/02_script_gen.py`
- Create: `scripts/08_manual_publish_notice.py`
- Create: `scripts/pipeline.py`
- Modify: `episodes/ep01_superpowers.json` (02_script_gen.py가 실제 생성한 내용으로 덮어씀)

**Interfaces:**
- Consumes: 이전 태스크의 모든 함수 (`generate_pose`, `generate_props`, `generate_narration_with_captions`, `compose_episode`, `send_for_review`)
- Produces: `episodes/candidates.json` (01), 완성된 `episodes/{episode_id}.json` (02)

- [ ] **Step 1: `01_research.py` 작성**

```python
# scripts/01_research.py
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

RESEARCH_PROMPT = """Claude Code / AI 코딩 도구 관련 최신 트렌드 소재를 3~5개 찾아줘.
각 소재는 아래 JSON 배열 형식으로만 응답해:
[{{"title": "...", "hook_angle": "...", "why_now": "..."}}]
소재는 실제로 화제성 있는 최근 오픈소스 프로젝트/기능이어야 하고, GitHub 스타 수 등 구체적 숫자를 hook_angle에 포함시켜줘."""


def research_candidates(client: genai.Client, model: str) -> list[dict]:
    interaction = client.interactions.create(
        model=model,
        input=RESEARCH_PROMPT,
        tools=[{"type": "google_search"}],
    )
    text = interaction.output_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def main():
    settings = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    candidates = research_candidates(client, settings["gemini_model_text"])

    out_path = ROOT / "episodes" / "candidates.json"
    out_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out_path}")
    for c in candidates:
        print(f"- {c['title']}: {c['hook_angle']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실제 실행 (실비용 미미, Gemini 텍스트 호출 1회)**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/python scripts/01_research.py
```
Expected: `episodes/candidates.json` 생성, 후보 목록 콘솔 출력. **사람 개입 지점 ①** — EP.1은 이미 DESIGN.md에서 "Superpowers 플러그인"으로 확정되어 있으므로 이번 실행은 검증용이며 실제 소재 선택에는 영향 없음

- [ ] **Step 3: `02_script_gen.py` 작성**

```python
# scripts/02_script_gen.py
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SCRIPT_PROMPT_TEMPLATE = """다음 주제로 인스타 릴스 나레이션 대본을 작성해줘: {title}

구조: 후킹(0~2초, 아래 표의 기법 중 하나 이상 적용) - 문제 - 소개 - 포인트 1~3개 - CTA
후킹 기법표:
- 숫자 충격: "다들 이거 몰라요" 대신 "깃허브 스타 7만 9천 개, 근데 아직도 모르는 사람 많더라고요"
- 부정 프레이밍: "이거 알려드릴게요" 대신 "이거 모르고 Claude 쓰면 절반만 쓰는 거예요"
- 궁금증 갭: "이런 기능이 있어요" 대신 "AI가 스스로 스킬을 만든다고요? 이거 실화예요"

아래 JSON 형식으로만 응답해 (다른 텍스트 없이):
{{
  "title": "{title}",
  "narration_script": "전체 나레이션 텍스트",
  "captions": ["자막 구간1", "자막 구간2"],
  "expression_cues": [
    {{"pose": "base", "start": 0, "duration": 3}},
    {{"pose": "pointing", "start": 3, "duration": 5}}
  ],
  "props_prompt": "flat vector cartoon illustration style, clean black outlines, soft flat colors, white background, no shadows: {{episode_specific_objects}}, arranged in a small grid, matching the art style of a friendly cartoon presenter character"
}}
pose 값은 반드시 다음 중 하나여야 해: base, surprised, nodding, pointing, questioning, celebrating"""


def generate_script(client: genai.Client, model: str, title: str) -> dict:
    interaction = client.interactions.create(
        model=model,
        input=SCRIPT_PROMPT_TEMPLATE.format(title=title),
    )
    text = interaction.output_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", required=True, help="output episode id, e.g. ep01_superpowers")
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    settings = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    script = generate_script(client, settings["gemini_model_text"], args.title)

    out_path = ROOT / "episodes" / f"{args.episode}.json"
    out_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 실제 실행 — EP.1 대본 생성 (기존 fixture 덮어씀)**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/python scripts/02_script_gen.py --episode ep01_superpowers --title "Superpowers 플러그인 (깃허브 스타 약 7만 9천 개)"
```
Expected: `episodes/ep01_superpowers.json`이 실제 대본/큐로 갱신됨. 내용을 사람이 검토(오탈자, pose 값 유효성)

- [ ] **Step 5: `08_manual_publish_notice.py` 작성**

```python
# scripts/08_manual_publish_notice.py
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Bot

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


async def notify_ready_to_publish() -> int:
    ready_dir = ROOT / "output" / "ready_to_publish"
    videos = list(ready_dir.glob("*.mp4")) if ready_dir.exists() else []
    if not videos:
        print("[skip] no videos ready to publish")
        return 0

    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    await bot.send_message(
        chat_id=chat_id,
        text=f"이번 주 업로드할 {len(videos)}개 영상이 준비됐어요:\n" + "\n".join(v.name for v in videos),
    )
    return len(videos)


def main():
    count = asyncio.run(notify_ready_to_publish())
    print(f"[ok] notified for {count} videos")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: `pipeline.py` 오케스트레이터 작성**

```python
# scripts/pipeline.py
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / "venv" / "bin" / "python")

STEP_COMMANDS = {
    "research": lambda ep: [PY, "scripts/01_research.py"],
    "script": lambda ep: [PY, "scripts/02_script_gen.py", "--episode", ep, "--title", _episode_title(ep)],
    "character": lambda ep: [PY, "scripts/03_generate_character.py", "--pose", "all"],
    "props": lambda ep: [PY, "scripts/04_generate_props.py", "--episode", ep],
    "narrate": lambda ep: None,  # inline, see run_narrate
    "compose": lambda ep: [PY, "scripts/06_compose.py", "--episode", ep],
    "review": lambda ep: [PY, "scripts/07_review_bot.py", "--episode", ep, "--caption", f"{ep} 검토 요청"],
}


def _episode_title(ep: str) -> str:
    path = ROOT / "episodes" / f"{ep}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("title", ep)
    return ep


def run_narrate(ep: str) -> None:
    episode = json.loads((ROOT / "episodes" / f"{ep}.json").read_text(encoding="utf-8"))
    settings = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    code = (
        "import asyncio, sys; sys.path.insert(0, 'scripts'); "
        "from importlib import import_module; narration = import_module('05_narration'); "
        f"asyncio.run(narration.generate_narration_with_captions({episode['narration_script']!r}, "
        f"'output/narration/{ep}.mp3', 'output/narration/{ep}.srt', {settings['tts_voice']!r}))"
    )
    subprocess.run([PY, "-c", code], cwd=ROOT, check=True)


def run_step(step: str, episode: str) -> None:
    if step == "narrate":
        run_narrate(episode)
        return
    cmd = STEP_COMMANDS[step](episode)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", required=True, choices=[*STEP_COMMANDS.keys(), "all"])
    parser.add_argument("--episode", required=False)
    args = parser.parse_args()

    if args.step == "all":
        for step in ["script", "character", "props", "narrate", "compose", "review"]:
            print(f"=== step: {step} ===")
            run_step(step, args.episode)
    else:
        run_step(args.step, args.episode)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: EP.1 엔드투엔드 실행 (character/props는 이미 생성되어 스킵됨 — 비용 재발생 없음)**

```bash
cd /Users/cheonhyeonjun/insta_auto
venv/bin/python scripts/pipeline.py --step all --episode ep01_superpowers
```
Expected: script → character(스킵) → props(스킵) → narrate → compose → review 순서로 진행. review 단계에서 사용자가 텔레그램 버튼 클릭 필요. 최종적으로 `output/ready_to_publish/ep01_superpowers_final.mp4` 존재 확인

- [ ] **Step 8: 발행 대기 알림 테스트**

```bash
venv/bin/python scripts/08_manual_publish_notice.py
```
Expected: 텔레그램에 "이번 주 업로드할 1개 영상이 준비됐어요" 알림 도착 확인

- [ ] **Step 9: 커밋**

```bash
git add scripts/01_research.py scripts/02_script_gen.py scripts/08_manual_publish_notice.py scripts/pipeline.py episodes/
git commit -m "feat: add research/script-gen/pipeline orchestrator, complete EP.1 end-to-end run"
```

---

### Task 8: 인스타 AI 생성 콘텐츠 고지 문구 확정

**Files:**
- Create: `docs/instagram_disclosure.md`

이 태스크는 코드가 아니라 카피 문구 확정이 결과물이다. 실행자는 아래 3개 후보를 문서로 정리하고, 최종안은 사용자 승인을 받아 `docs/instagram_disclosure.md`에 확정 표시한다.

- [ ] **Step 1: 후보 문구 작성**

```markdown
# 인스타 AI 생성 콘텐츠 고지 문구 (안)

## 프로필 소개란 후보
1. "🤖 이 계정의 영상은 AI로 제작됩니다"
2. "AI가 만든 콘텐츠예요 (기획/검수는 사람이 직접)"
3. "AI-generated content / 기획·감수: 사람"

## 캡션 하단 고정 문구 후보
1. "\n\n※ 이 영상은 AI로 생성되었습니다"
2. "\n\n🤖 AI 생성 콘텐츠 | 대본·검수: 직접"

## 결정 필요
- [ ] 사용자가 위 후보 중 최종안 선택 또는 직접 작성
- [ ] Meta 정책(AI 생성 콘텐츠 라벨링 가이드라인) 재확인 후 최종 확정
```

- [ ] **Step 2: 사용자에게 후보 제시하고 최종 문구 확정받아 문서에 반영**

- [ ] **Step 3: 커밋**

```bash
git add docs/instagram_disclosure.md
git commit -m "docs: draft instagram AI content disclosure copy candidates"
```
