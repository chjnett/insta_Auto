import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from importlib import import_module

compose = import_module("06_compose")


def test_build_filter_complex_basic_structure():
    character_cues = [
        {"pose": "base", "start": 0, "duration": 3},
        {"pose": "pointing", "start": 3, "duration": 5},
    ]
    props_cues = [
        {"index": 0, "start": 0, "duration": 4},
        {"index": 1, "start": 4, "duration": 4},
    ]
    result = compose.build_filter_complex(character_cues, props_cues, "output/narration/ep01.srt")

    assert "color=white:s=1080x1920:d=15[bg0]" in result
    # 2 props overlays + 2 character overlays
    assert result.count("overlay=") == 4
    assert "subtitles=output/narration/ep01.srt" in result
    assert result.endswith("[v]")
    # props images occupy input indices 0..1 (scaled to full canvas width, top area)
    assert "[0:v]scale=1080:600[props0]" in result
    assert "[1:v]scale=1080:600[props1]" in result
    # character images occupy input indices 2..3, right after props
    assert "[2:v]scale=700:-1[char0]" in result
    assert "[3:v]scale=700:-1[char1]" in result
    # smaller subtitle font per user request, and readable-on-white styling
    assert "FontSize=32" in result
    assert "PrimaryColour=&H00000000" in result
    assert "MarginV=145" in result
    # bundled Black Han Sans (SIL OFL) via fontsdir, not relying on whatever
    # fallback font happens to be installed on the machine
    assert "fontsdir=assets/fonts" in result
    assert "FontName=Black Han Sans" in result


def test_build_filter_complex_empty_cues():
    result = compose.build_filter_complex([], [], "output/narration/ep01.srt")
    assert "subtitles=" in result
    assert "overlay=" not in result


def test_build_filter_complex_duration_matches_narration_length():
    # canvas duration must follow the actual narration length, not a fixed
    # 15s — a longer script (e.g. 26s) would otherwise get its audio cut off
    # by ffmpeg's -shortest once the 15s background stream ends
    result = compose.build_filter_complex([], [], "output/narration/ep01.srt", duration=26.5)
    assert "color=white:s=1080x1920:d=26.5[bg0]" in result
