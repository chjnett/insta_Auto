# reels-automation

인스타 릴스 자동 생성 파이프라인. 전체 설계는 [DESIGN.md](./DESIGN.md), 진행 상황/작업 지침은 [CLAUDE.md](./CLAUDE.md), 구현 계획은 [docs/superpowers/plans/](./docs/superpowers/plans/)를 참고.

## 요약
- 비주얼: Gemini(Nano Banana) 참조 이미지 기반 캐릭터 + 소품
- 리서치/대본: Gemini API (Anthropic API 미사용)
- 나레이션: edge-tts (SubMaker 자막 자동 싱크)
- 합성: ffmpeg (libass 포함 빌드 필요 — `homebrew-ffmpeg/ffmpeg/ffmpeg` 사용)
- 검토: 텔레그램 봇
- 발행: 현재는 수동 업로드

## 설치

```bash
# ffmpeg (libass 포함 빌드 — 기본 homebrew-core ffmpeg는 subtitles 필터 없음)
brew tap homebrew-ffmpeg/ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg

# Python 가상환경
/opt/homebrew/bin/python3.12 -m venv venv
venv/bin/pip install -r requirements.txt
```

`.env`에 다음 값 필요 (git에 커밋하지 않음):
```
GEMINI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## 비용 안전장치

모든 Gemini API 호출은 `scripts/budget_guard.py`를 거쳐 `logs/run_log.csv`에 누적 비용을 기록하고, `config/settings.json`의 `budget_limit_usd`를 초과하면 호출 전에 차단한다.

## 실행

```bash
venv/bin/python scripts/pipeline.py --step all --episode ep01_superpowers
```

개별 단계는 DESIGN.md 섹션 4.9 참고.
