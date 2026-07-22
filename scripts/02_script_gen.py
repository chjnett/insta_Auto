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
PROPS_SEGMENT_SECONDS = 5

SCRIPT_PROMPT_TEMPLATE = """다음 주제로 인스타 릴스 나레이션 대본을 작성해줘: {title}

이 주제에 대한 정확한 사실(실제 기능, 실제 사용법, 실제 숫자)을 검색해서 확인한 뒤 반영해.

구조: 후킹(첫 문장) - 문제 - 소개 - 포인트 1~3개(구체적인 기능/사용법을 짧고 명확하게) - CTA
narration_script 전체 길이는 반드시 {target_chars}자 내외(공백 포함)로 맞춰줘. 이건 실제 음성 낭독 속도로 약 {target_seconds}초 분량이라 길이를 넘기면 릴스로 쓸 수 없어. 길다고 좋은 게 아니라, 정확히 이 분량 안에서 핵심만 압축해서 담아야 해.

후킹 문장(가장 처음)은 아래 표의 기법 중 하나 이상을 반드시 적용해:
- 숫자 충격: "다들 이거 몰라요" 대신 "깃허브 스타 7만 9천 개, 근데 아직도 모르는 사람 많더라고요"
- 부정 프레이밍: "이거 알려드릴게요" 대신 "이거 모르고 Claude 쓰면 절반만 쓰는 거예요"
- 궁금증 갭: "이런 기능이 있어요" 대신 "AI가 스스로 스킬을 만든다고요? 이거 실화예요"
- 대조/반전: "설명드릴게요" 대신 "다들 어렵다는데, 사실 명령어 한 줄이면 끝나요"
- 즉시 행동 유도: "저장하세요" 대신 "지금 안 보면 다음 주에 또 검색하게 될걸요"

props_prompts는 4개: 영상 흐름(후킹/문제 - 소개 - 포인트 - CTA)에 맞춰 서로 다른 소품 세트 4개로 나눠줘. 매번 이미지를 더 생성해도 괜찮으니 아끼지 말 것 — 세트 수를 줄이지 마.
각 소품 세트는 반드시 6~8개의 단순한 사물/아이콘을 나열해 (기존보다 더 풍성하게, 예: 키보드, 톱니바퀴, 별, 체크마크, 마법봉, 로봇팔, 반짝이는 스파클, 자물쇠, 방패, 로켓, 트로피, 돋보기, 전구, 클립보드, 터미널 창, 클라우드 아이콘). 절대 하지 말 것: 글자/텍스트가 들어간 화면·카드·팝업·UI 목업을 그리지 말 것, 사람 캐릭터(우리 캐릭터 포함)를 넣지 말 것. 순수하게 텍스트 없는 단순 아이콘 오브젝트 나열만 허용돼.

아래 JSON 형식으로만 응답해 (다른 텍스트 없이, 마크다운 코드블록 없이):
{{
  "title": "{title}",
  "narration_script": "전체 나레이션 텍스트 ({target_chars}자 내외)",
  "captions": ["자막 구간1", "자막 구간2"],
  "props_prompts": [
    "flat vector cartoon illustration style, clean black outlines, soft flat colors, white background, no shadows: {{episode_specific_objects_1}}, arranged in a small grid, matching the art style of a friendly cartoon presenter character. No text, no letters, no words, no UI screens or app mockups, no human figures or people — icons only",
    "flat vector cartoon illustration style, clean black outlines, soft flat colors, white background, no shadows: {{episode_specific_objects_2}}, arranged in a small grid, matching the art style of a friendly cartoon presenter character. No text, no letters, no words, no UI screens or app mockups, no human figures or people — icons only",
    "flat vector cartoon illustration style, clean black outlines, soft flat colors, white background, no shadows: {{episode_specific_objects_3}}, arranged in a small grid, matching the art style of a friendly cartoon presenter character. No text, no letters, no words, no UI screens or app mockups, no human figures or people — icons only",
    "flat vector cartoon illustration style, clean black outlines, soft flat colors, white background, no shadows: {{episode_specific_objects_4}}, arranged in a small grid, matching the art style of a friendly cartoon presenter character. No text, no letters, no words, no UI screens or app mockups, no human figures or people — icons only"
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


def build_cues(duration: float, n_props_sets: int = 4) -> tuple[list[dict], list[dict]]:
    """Evenly distribute character poses and props sets across the real
    measured narration duration. Timing must come from the real audio, not
    from an LLM's guess about how long its own text will take to speak."""
    n_expr = min(len(EXPRESSION_CYCLE), max(2, round(duration / 5)))
    expr_step = duration / n_expr
    expression_cues = [
        {"pose": EXPRESSION_CYCLE[i % len(EXPRESSION_CYCLE)], "start": round(i * expr_step, 2), "duration": round(expr_step, 2)}
        for i in range(n_expr)
    ]

    # Cycle through the generated props sets (n_props_sets, default 4) in
    # short segments so the top icons visibly change often, rather than one
    # static chunk each.
    n_props = max(n_props_sets, round(duration / PROPS_SEGMENT_SECONDS))
    props_step = duration / n_props
    props_cues = [
        {"index": i % n_props_sets, "start": round(i * props_step, 2), "duration": round(props_step, 2)}
        for i in range(n_props)
    ]
    return expression_cues, props_cues


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
