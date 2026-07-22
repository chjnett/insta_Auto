import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build_filter_complex(expression_cues, srt_path,
                          canvas_w=1080, canvas_h=1920,
                          props_h=600, char_w=700, char_y=950):
    filters = [
        f"[0:v]scale={canvas_w}:{props_h}[props]",
        f"color=white:s={canvas_w}x{canvas_h}:d=15[bg]",
        "[bg][props]overlay=0:0[bg1]",
    ]
    prev = "bg1"
    char_x = (canvas_w - char_w) // 2
    for i, cue in enumerate(expression_cues):
        # input order: 0=props, 1..N=character images, N+1=narration, N+2=bgm
        input_idx = i + 1
        label = f"bg{i + 2}"
        filters.append(f"[{input_idx}:v]scale={char_w}:-1[char{i}]")
        filters.append(
            f"[{prev}][char{i}]overlay={char_x}:{char_y}:"
            f"enable='between(t,{cue['start']},{cue['start'] + cue['duration']})'[{label}]"
        )
        prev = label
    # MarginV=145 (not 850) is intentional: ffmpeg's subtitles filter scales
    # MarginV by ~6.7x relative to the actual canvas height when the source
    # is a plain .srt with no embedded PlayRes, so a naive pixel-space value
    # (e.g. 850 for the 640-900px caption band) is pushed off-screen entirely.
    # 145 was calibrated empirically to land text inside the 640-900px band.
    filters.append(
        f"[{prev}]subtitles={srt_path}:force_style="
        f"'FontName=NanumSquareRound,FontSize=42,PrimaryColour=&H00000000,Alignment=2,MarginV=145'[v]"
    )
    return ";".join(filters)


def compose_episode(props_path, character_images, expression_cues,
                     narration_path, srt_path, bgm_path, output_path):
    filter_complex = build_filter_complex(expression_cues, srt_path)

    inputs = ["-loop", "1", "-i", str(props_path)]
    for img in character_images:
        inputs += ["-loop", "1", "-i", str(img)]
    inputs += ["-i", str(narration_path), "-i", str(bgm_path)]

    audio_filter = (
        f"[{len(character_images)+1}:a]volume=1.5[narr];"
        f"[{len(character_images)+2}:a]volume=0.28[bgm];"
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
    props_path = ROOT / "assets" / "props" / args.episode / "props.png"
    character_images = [ROOT / "assets" / "character" / f"{c['pose']}.png" for c in episode["expression_cues"]]
    narration_path = ROOT / "output" / "narration" / f"{args.episode}.mp3"
    srt_path = ROOT / "output" / "narration" / f"{args.episode}.srt"
    bgm_path = ROOT / "assets" / "bgm" / "default.mp3"
    output_path = ROOT / "output" / "final" / f"{args.episode}_final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    compose_episode(props_path, character_images, episode["expression_cues"],
                     narration_path, srt_path, bgm_path, output_path)


if __name__ == "__main__":
    main()
