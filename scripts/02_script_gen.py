import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

import budget_guard

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Calibrated empirically against ko-KR-InJoonNeural at rate=-8% (see Task 5/6
# debugging): ~6.7 characters/second of narration_script text. Gemini cannot
# know edge-tts's real speaking pace, so it must not be trusted to self-report
# durations — only to write text of roughly the right *character* length.
CHARS_PER_SECOND = 6.7
TARGET_SECONDS = 28

EXPRESSION_CYCLE = ["surprised", "questioning", "pointing", "nodding", "celebrating"]

SCRIPT_PROMPT_TEMPLATE = """다음 주제로 인스타 릴스 나레이션 대본을 작성해줘: {title}

이 주제에 대한 정확한 사실(실제 기능, 실제 사용법, 실제 숫자)을 검색해서 확인한 뒤 반영해.

구조: 후킹(첫 문장, 문제 제기형) - 문제 부연 - 소개 - 포인트 1~3개(구체적인 기능/사용법을 짧고 명확하게) - CTA
narration_script 전체 길이는 반드시 {target_chars}자 내외(공백 포함)로 맞춰줘. 이건 실제 음성 낭독 속도로 약 {target_seconds}초 분량이라 길이를 넘기면 릴스로 쓸 수 없어. 길다고 좋은 게 아니라, 정확히 이 분량 안에서 핵심만 압축해서 담아야 해.

**후킹 문장(가장 처음)은 반드시 "문제 제기형"으로 시작해야 해** — 시청자가 실제로 겪을 법한 구체적인 답답함/실수/불편함을 바로 찌르면서 시작해. 숫자나 통계를 던지는 것으로 시작하지 말고, 공감 가는 문제 상황을 먼저 던진 다음 반전으로 이어가는 방식을 우선으로 써. 아래 표에서 **부정 프레이밍 또는 궁금증 갭을 우선 적용**하고, 숫자 충격은 문제 제기 뒤에 보조적으로만 섞어:
- 부정 프레이밍 (우선): "이거 알려드릴게요" 대신 "이거 모르고 Claude 쓰면 절반만 쓰는 거예요"
- 궁금증 갭 (우선): "이런 기능이 있어요" 대신 "AI가 스스로 스킬을 만든다고요? 이거 실화예요"
- 공감형 문제 제기 (우선, 새로 추가): "설명드릴게요" 대신 "이거 때문에 밤새 디버깅한 적 있으시죠?" 처럼 구체적인 괴로운 상황을 직접 묘사
- 대조/반전 (보조): "설명드릴게요" 대신 "다들 어렵다는데, 사실 명령어 한 줄이면 끝나요"
- 숫자 충격 (보조, 문제 제기와 결합해서만 사용): "다들 이거 몰라요" 대신 "매번 똑같은 실수 반복하는데, 이미 7만 9천 명이 해결법 찾았더라고요"
- 즉시 행동 유도 (CTA에 사용): "저장하세요" 대신 "지금 안 보면 다음 주에 또 검색하게 될걸요"

후킹은 뻔하지 않고 흥미롭게 — 진부한 표현("여러분", "오늘 소개할") 금지, 실제 대화하듯 구체적인 상황 묘사로 시작.

**props_prompts는 captions 배열과 정확히 같은 개수여야 하고, 인덱스가 1:1로 대응해야 해** (props_prompts[i]는 captions[i]가 화면에 떠 있는 동안 보여줄 소품 세트). 각 세트는 그 문장이 말하는 "구체적인 내용"을 직접 시각화해야 해 — 예를 들어 "TDD 테스트 강제"라고 말하는 문장이면 시험관/체크마크/빨간X초록체크 같은 테스트 관련 아이콘을, "/plugin 명령어로 설치"라고 말하는 문장이면 터미널/다운로드 화살표/설치 관련 아이콘을 써야 해. 뭉뚱그린 범용 아이콘(키보드, 별, 반짝이만 나열하는 식)은 피하고, 그 순간 실제로 언급되는 개념과 최대한 직접적으로 연결되는 사물을 골라.
각 소품 세트는 4~6개의 단순한 사물/아이콘을 나열해. 절대 하지 말 것: 글자/텍스트가 들어간 화면·카드·팝업·UI 목업을 그리지 말 것, 사람 캐릭터(우리 캐릭터 포함)를 넣지 말 것. 순수하게 텍스트 없는 단순 아이콘 오브젝트 나열만 허용돼.

아래 JSON 형식으로만 응답해 (다른 텍스트 없이, 마크다운 코드블록 없이). captions와 props_prompts 개수는 실제로 필요한 문장 수에 맞춰 늘리거나 줄여도 되지만 두 배열의 길이는 항상 같아야 해:
{{
  "title": "{title}",
  "narration_script": "전체 나레이션 텍스트 ({target_chars}자 내외)",
  "captions": ["자막 구간1", "자막 구간2", "..."],
  "props_prompts": [
    "flat vector cartoon illustration style, clean black outlines, soft flat colors, white background, no shadows: {{objects specifically depicting what captions[0] says}}, arranged in a small grid, matching the art style of a friendly cartoon presenter character. No text, no letters, no words, no UI screens or app mockups, no human figures or people — icons only",
    "flat vector cartoon illustration style, clean black outlines, soft flat colors, white background, no shadows: {{objects specifically depicting what captions[1] says}}, arranged in a small grid, matching the art style of a friendly cartoon presenter character. No text, no letters, no words, no UI screens or app mockups, no human figures or people — icons only",
    "..."
  ]
}}"""


def generate_script(client: genai.Client, model: str, title: str, settings: dict) -> dict:
    budget_guard.check_and_record("02_script_gen", "text", settings)
    target_chars = int(CHARS_PER_SECOND * TARGET_SECONDS)
    interaction = client.interactions.create(
        model=model,
        input=SCRIPT_PROMPT_TEMPLATE.format(title=title, target_chars=target_chars, target_seconds=TARGET_SECONDS),
        tools=[{"type": "google_search"}],
    )
    text = interaction.output_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def build_expression_cues(duration: float) -> list[dict]:
    """Evenly distribute character poses across the real measured narration
    duration. Timing must come from the real audio, not from an LLM's guess
    about how long its own text will take to speak."""
    n_expr = min(len(EXPRESSION_CYCLE), max(2, round(duration / 5)))
    expr_step = duration / n_expr
    return [
        {"pose": EXPRESSION_CYCLE[i % len(EXPRESSION_CYCLE)], "start": round(i * expr_step, 2), "duration": round(expr_step, 2)}
        for i in range(n_expr)
    ]


def build_props_cues_from_segments(segments: list[dict]) -> list[dict]:
    """One props/icon set per caption, shown for exactly the time that
    caption's audio plays (segments comes from
    05_narration.generate_narration_gemini_per_sentence). Replaces the old
    generic even-split cycling through a fixed 4 sets, which showed
    generic icons unrelated to whatever was being said at that moment."""
    return [
        {"index": i, "start": seg["start"], "duration": seg["duration"]}
        for i, seg in enumerate(segments)
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", required=True, help="output episode id, e.g. ep01_superpowers")
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    settings = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    script = generate_script(client, settings["gemini_model_text"], args.title, settings)

    out_path = ROOT / "episodes" / f"{args.episode}.json"
    out_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out_path} (cues not yet computed — run narration step first, then merge)")


if __name__ == "__main__":
    main()
