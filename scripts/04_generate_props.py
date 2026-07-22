import argparse
import base64
import io
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from PIL import Image

import budget_guard

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def generate_props(episode_id: str, props_prompt: str, client: genai.Client, settings: dict) -> Path:
    out_dir = ROOT / "assets" / "props" / episode_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "props.png"

    budget_guard.check_and_record("04_generate_props", "image", settings)
    interaction = client.interactions.create(
        model=settings["gemini_model_image"],
        input=[{"type": "text", "text": props_prompt}],
    )
    raw_bytes = base64.b64decode(interaction.output_image.data)
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.save(out_path, "PNG")
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
