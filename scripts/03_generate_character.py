import argparse
import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

import budget_guard

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

    budget_guard.check_and_record("03_generate_character", "image", settings)
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
