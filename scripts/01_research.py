import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

import budget_guard

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

RESEARCH_PROMPT = """Claude Code / AI 코딩 도구 관련 최신 트렌드 소재를 3~5개 찾아줘.
각 소재는 아래 JSON 배열 형식으로만 응답해:
[{"title": "...", "hook_angle": "...", "why_now": "..."}]
소재는 실제로 화제성 있는 최근 오픈소스 프로젝트/기능이어야 하고, GitHub 스타 수 등 구체적 숫자를 hook_angle에 포함시켜줘."""


def research_candidates(client: genai.Client, model: str, settings: dict) -> list[dict]:
    budget_guard.check_and_record("01_research", "text", settings)
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
    candidates = research_candidates(client, settings["gemini_model_text"], settings)

    out_path = ROOT / "episodes" / "candidates.json"
    out_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out_path}")
    for c in candidates:
        print(f"- {c['title']}: {c['hook_angle']}")


if __name__ == "__main__":
    main()
