import argparse
import base64
import io
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from PIL import Image, ImageChops

import budget_guard

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _trim_and_save_png(raw_bytes: bytes, out_path: Path, padding: int = 20, threshold: int = 20) -> None:
    """Decode whatever format Gemini returned, trim uniform white margins, save as real PNG.

    Uses a difference threshold rather than a raw getbbox() because JPEG-encoded
    output introduces compression noise into nominally-white background pixels,
    which makes an exact-white diff bbox span the entire image.
    """
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg).convert("L")
    mask = diff.point(lambda p: 255 if p > threshold else 0)
    bbox = mask.getbbox()
    if bbox:
        left, top, right, bottom = bbox
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(img.width, right + padding)
        bottom = min(img.height, bottom + padding)
        img = img.crop((left, top, right, bottom))
    img.save(out_path, "PNG")


def get_client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def generate_pose(pose_key: str, client: genai.Client, cfg: dict, settings: dict, assets_dir: Path) -> Path:
    out_path = assets_dir / f"{pose_key}.png"
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
    _trim_and_save_png(base64.b64decode(image_b64), out_path)
    print(f"[ok] wrote {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", default="character",
                         help="character id: matches config/{id}.json and assets/{id}/ (default: 'character')")
    parser.add_argument("--pose", default="base", help="pose key from the character config, or 'all'")
    args = parser.parse_args()

    cfg = load_json(ROOT / "config" / f"{args.character}.json")
    settings = load_json(ROOT / "config" / "settings.json")
    client = get_client()
    assets_dir = ROOT / "assets" / args.character
    assets_dir.mkdir(parents=True, exist_ok=True)

    if args.pose == "all":
        for pose_key in cfg["poses"]:
            generate_pose(pose_key, client, cfg, settings, assets_dir)
    else:
        generate_pose(args.pose, client, cfg, settings, assets_dir)


if __name__ == "__main__":
    main()
