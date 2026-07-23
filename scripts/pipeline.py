import argparse
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

    audio_path = ROOT / "output" / "narration" / f"{episode}.wav"
    srt_path = ROOT / "output" / "narration" / f"{episode}.srt"
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    # Per-sentence Gemini TTS: gives exact per-caption durations, which
    # build_props_cues_from_segments uses to show each props/icon set for
    # precisely the time its matching caption is on screen.
    segments = narration.generate_narration_gemini_per_sentence(
        episode_data["captions"], audio_path, srt_path,
        settings["gemini_tts_voice_male"], settings["gemini_model_tts"], settings,
    )
    total_duration = segments[-1]["start"] + segments[-1]["duration"]

    episode_data["expression_cues"] = script_gen.build_expression_cues(total_duration)
    episode_data["props_cues"] = script_gen.build_props_cues_from_segments(segments)
    (ROOT / "episodes" / f"{episode}.json").write_text(
        json.dumps(episode_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[ok] narration duration {total_duration:.2f}s, {len(segments)} props sets (1 per caption)")


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
