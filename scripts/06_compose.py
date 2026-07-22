import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build_filter_complex(character_cues, props_cues, srt_path,
                          canvas_w=1080, canvas_h=1920,
                          props_h=600, char_w=700, char_y=950, duration=15):
    props_w = canvas_w
    filters = [f"color=white:s={canvas_w}x{canvas_h}:d={duration}[bg0]"]
    prev = "bg0"
    input_idx = 0

    for i, cue in enumerate(props_cues):
        filters.append(f"[{input_idx}:v]scale={props_w}:{props_h}[props{i}]")
        label = f"bgp{i}"
        filters.append(
            f"[{prev}][props{i}]overlay=0:0:"
            f"enable='between(t,{cue['start']},{cue['start'] + cue['duration']})'[{label}]"
        )
        prev = label
        input_idx += 1

    char_x = (canvas_w - char_w) // 2
    for i, cue in enumerate(character_cues):
        filters.append(f"[{input_idx}:v]scale={char_w}:-1[char{i}]")
        label = f"bgc{i}"
        filters.append(
            f"[{prev}][char{i}]overlay={char_x}:{char_y}:"
            f"enable='between(t,{cue['start']},{cue['start'] + cue['duration']})'[{label}]"
        )
        prev = label
        input_idx += 1

    # MarginV=145 (not a naive pixel value like 850) is intentional: ffmpeg's
    # subtitles filter scales MarginV by ~6.7x relative to canvas height when
    # the source is a plain .srt with no embedded PlayRes, so it was
    # calibrated empirically to land text inside the 640-900px caption band.
    # PrimaryColour=black because on this white canvas the ASS default
    # (white fill / black outline) renders as near-invisible outlined text.
    filters.append(
        f"[{prev}]subtitles={srt_path}:force_style="
        f"'FontName=NanumSquareRound,FontSize=32,PrimaryColour=&H00000000,Alignment=2,MarginV=145'[v]"
    )
    return ";".join(filters)


def _get_audio_duration(path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def compose_episode(props_images, props_cues, character_images, character_cues,
                     narration_path, srt_path, bgm_path, output_path):
    duration = _get_audio_duration(narration_path) + 0.5
    filter_complex = build_filter_complex(character_cues, props_cues, srt_path, duration=duration)

    inputs = []
    for img in props_images:
        inputs += ["-loop", "1", "-i", str(img)]
    for img in character_images:
        inputs += ["-loop", "1", "-i", str(img)]
    inputs += ["-i", str(narration_path), "-i", str(bgm_path)]

    n_visual = len(props_images) + len(character_images)
    audio_filter = (
        f"[{n_visual}:a]volume=1.5[narr];"
        f"[{n_visual + 1}:a]volume=0.28[bgm];"
        f"[narr][bgm]amix=inputs=2:duration=first[a]"
    )

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", f"{filter_complex};{audio_filter}",
        "-map", "[v]", "-map", "[a]",
        "-shortest", str(output_path),
    ]
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", required=True)
    args = parser.parse_args()

    episode = json.loads((ROOT / "episodes" / f"{args.episode}.json").read_text(encoding="utf-8"))
    props_dir = ROOT / "assets" / "props" / args.episode
    props_images = [props_dir / f"props_{c['index']}.png" for c in episode["props_cues"]]
    character_images = [ROOT / "assets" / "character" / f"{c['pose']}.png" for c in episode["expression_cues"]]
    narration_path = ROOT / "output" / "narration" / f"{args.episode}.mp3"
    srt_path = ROOT / "output" / "narration" / f"{args.episode}.srt"
    bgm_path = ROOT / "assets" / "bgm" / "default.mp3"
    output_path = ROOT / "output" / "final" / f"{args.episode}_final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    compose_episode(props_images, episode["props_cues"], character_images, episode["expression_cues"],
                     narration_path, srt_path, bgm_path, output_path)


if __name__ == "__main__":
    main()
