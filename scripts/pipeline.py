import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / "venv" / "bin" / "python")
sys.path.insert(0, str(ROOT / "scripts"))


def _episode_title(ep: str) -> str:
    path = ROOT / "episodes" / f"{ep}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("title", ep)
    return ep


def run_research() -> None:
    subprocess.run([PY, "scripts/01_research.py"], cwd=ROOT, check=True)


def run_script(episode: str) -> None:
    subprocess.run(
        [PY, "scripts/02_script_gen.py", "--episode", episode, "--title", _episode_title(episode)],
        cwd=ROOT, check=True,
    )


def run_character() -> None:
    subprocess.run([PY, "scripts/03_generate_character.py", "--pose", "all"], cwd=ROOT, check=True)


def run_props(episode: str) -> None:
    subprocess.run([PY, "scripts/04_generate_props.py", "--episode", episode], cwd=ROOT, check=True)


def run_narrate(episode: str) -> None:
    from importlib import import_module
    narration = import_module("05_narration")
    script_gen = import_module("02_script_gen")

    episode_data = json.loads((ROOT / "episodes" / f"{episode}.json").read_text(encoding="utf-8"))
    settings = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))

    audio_path = ROOT / "output" / "narration" / f"{episode}.mp3"
    srt_path = ROOT / "output" / "narration" / f"{episode}.srt"
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    asyncio.run(narration.generate_narration_with_captions(
        episode_data["narration_script"], audio_path, srt_path,
        settings["tts_voice"], rate=settings["tts_rate"],
    ))

    duration_result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    duration = float(duration_result.stdout.strip())
    expression_cues, props_cues = script_gen.build_cues(duration)
    episode_data["expression_cues"] = expression_cues
    episode_data["props_cues"] = props_cues
    (ROOT / "episodes" / f"{episode}.json").write_text(
        json.dumps(episode_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[ok] narration duration {duration:.2f}s, cues recomputed")


def run_compose(episode: str) -> None:
    subprocess.run([PY, "scripts/06_compose.py", "--episode", episode], cwd=ROOT, check=True)


def run_review(episode: str) -> None:
    subprocess.run(
        [PY, "scripts/07_review_bot.py", "--episode", episode, "--caption", f"{episode} 검토 요청"],
        cwd=ROOT, check=True,
    )


def run_notice() -> None:
    subprocess.run([PY, "scripts/08_manual_publish_notice.py"], cwd=ROOT, check=True)


STEP_FUNCS = {
    "research": lambda ep: run_research(),
    "script": run_script,
    "character": lambda ep: run_character(),
    "props": run_props,
    "narrate": run_narrate,
    "compose": run_compose,
    "review": run_review,
    "notice": lambda ep: run_notice(),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", required=True, choices=[*STEP_FUNCS.keys(), "all"])
    parser.add_argument("--episode", required=False)
    args = parser.parse_args()

    if args.step == "all":
        for step in ["script", "character", "props", "narrate", "compose", "review"]:
            print(f"=== step: {step} ===")
            STEP_FUNCS[step](args.episode)
    else:
        STEP_FUNCS[args.step](args.episode)


if __name__ == "__main__":
    main()
