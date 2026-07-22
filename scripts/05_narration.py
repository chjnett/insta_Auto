import argparse
import asyncio
import json
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent.parent

SAMPLE_TEXT = "깃허브 스타 7만 9천 개, 근데 아직도 모르는 사람 많더라고요. 이거 모르고 Claude 쓰면 절반만 쓰는 거예요."


async def generate_narration_with_captions(text: str, output_audio: Path, output_srt: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, boundary="WordBoundary")
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
