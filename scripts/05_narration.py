import argparse
import asyncio
import base64
import datetime
import json
import os
import wave
from pathlib import Path

import edge_tts
from dotenv import load_dotenv
from google import genai

import budget_guard

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SAMPLE_TEXT = "깃허브 스타 7만 9천 개, 근데 아직도 모르는 사람 많더라고요. 이거 모르고 Claude 쓰면 절반만 쓰는 거예요."


async def generate_narration_with_captions(text: str, output_audio: Path, output_srt: Path, voice: str,
                                            rate: str = "-8%", pitch: str = "+0Hz", volume: str = "+0%") -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, boundary="WordBoundary",
                                        rate=rate, pitch=pitch, volume=volume)
    submaker = edge_tts.SubMaker()

    with open(output_audio, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())


def _srt_timestamp(seconds: float) -> str:
    td = datetime.timedelta(seconds=max(0.0, seconds))
    total_ms = round(td.total_seconds() * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_srt_from_captions(captions: list[str], duration: float) -> str:
    """Gemini TTS returns no word/sentence timestamps (unlike edge-tts's
    SubMaker), so caption timing is approximated by splitting the real
    audio duration evenly across the sentence-level `captions` list — the
    same even-distribution approach already used for expression/props cues."""
    n = len(captions)
    step = duration / n
    lines = []
    for i, caption in enumerate(captions):
        start = i * step
        end = (i + 1) * step
        lines.append(
            f"{i + 1}\n{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n{caption}\n"
        )
    return "\n".join(lines)


def _gemini_tts_pcm(client: genai.Client, text: str, voice: str, model: str, settings: dict) -> bytes:
    budget_guard.check_and_record("05_narration", "tts", settings)
    interaction = client.interactions.create(
        model=model,
        input=text,
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": voice}]},
    )
    return base64.b64decode(interaction.output_audio.data)


def generate_narration_gemini(text: str, captions: list[str], output_audio: Path, output_srt: Path,
                               voice: str, model: str, settings: dict) -> float:
    """Higher-quality narration via Gemini's native TTS model, in place of
    edge-tts, per user feedback that edge-tts voice quality was too low.
    Returns the resulting audio duration in seconds."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    pcm = _gemini_tts_pcm(client, text, voice, model, settings)
    with wave.open(str(output_audio), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm)

    duration = len(pcm) / (24000 * 2)
    output_srt.write_text(build_srt_from_captions(captions, duration), encoding="utf-8")
    return duration


def generate_narration_gemini_per_sentence(captions: list[str], output_audio: Path, output_srt: Path,
                                            voice: str, model: str, settings: dict) -> float:
    """Same Gemini TTS voice, but synthesized one API call per caption/sentence
    instead of one call for the whole script. This trades a few extra cheap
    TTS calls for *exact* text-audio sync: each caption's SRT timing is the
    real measured duration of the clip that speaks it, not a guess (the
    single-call + even-split approach in generate_narration_gemini() drifts
    out of sync because sentences don't take equal time to speak)."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    srt_lines = []
    all_pcm = bytearray()
    cursor = 0.0

    for i, caption in enumerate(captions):
        pcm = _gemini_tts_pcm(client, caption, voice, model, settings)
        seg_duration = len(pcm) / (24000 * 2)
        srt_lines.append(
            f"{i + 1}\n{_srt_timestamp(cursor)} --> {_srt_timestamp(cursor + seg_duration)}\n{caption}\n"
        )
        all_pcm += pcm
        cursor += seg_duration

    with wave.open(str(output_audio), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(bytes(all_pcm))

    output_srt.write_text("\n".join(srt_lines), encoding="utf-8")
    return cursor


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
        asyncio.run(generate_narration_with_captions(
            args.text, Path(args.out_audio), Path(args.out_srt), voice,
            rate=settings.get("tts_rate", "+0%"),
            pitch=settings.get("tts_pitch", "+0Hz"),
            volume=settings.get("tts_volume", "+0%"),
        ))


if __name__ == "__main__":
    main()
