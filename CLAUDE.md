# CLAUDE.md

이 프로젝트는 인스타 릴스 자동 생성 파이프라인입니다.
전체 설계는 DESIGN.md 를 참고하세요.

## 핵심 요약
- 비주얼: Gemini(Nano Banana) 참조 이미지 기반 캐릭터 + 소품
- 리서치/대본: Gemini API (Anthropic API는 사용하지 않음 — 텍스트 작업 전부 Gemini로 통일)
- 나레이션: edge-tts (SubMaker로 자막 자동 싱크)
- 합성: ffmpeg (build_filter_complex 동적 생성)
- 검토: 텔레그램 봇
- 발행: 현재는 수동 업로드, 메타 API는 후순위
- 사람 개입: 소재 선택 + 텔레그램 최종 승인, 그 외 전부 자동화

## API 키
- `.env`에 `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 준비되어 있음
- ANTHROPIC_API_KEY는 사용하지 않음

## 작업 시 참고
- 새 스크립트 작성 전 DESIGN.md의 디렉토리 구조(섹션 3)를 따를 것
- 모듈 번호(01~08) 순서를 유지할 것
