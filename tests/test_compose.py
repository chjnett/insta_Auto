import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from importlib import import_module

compose = import_module("06_compose")


def test_build_filter_complex_basic_structure():
    cues = [
        {"pose": "base", "start": 0, "duration": 3},
        {"pose": "pointing", "start": 3, "duration": 5},
    ]
    result = compose.build_filter_complex(cues, "output/narration/ep01.srt")

    assert "[0:v]scale=1080:600[props]" in result
    assert "color=white:s=1080x1920:d=15[bg]" in result
    assert result.count("overlay=") == 3  # props overlay + 2 char overlays
    assert "subtitles=output/narration/ep01.srt" in result
    assert result.endswith("[v]")
    # input order is props(0), then character images(1..N) — regression guard for the
    # off-by-one bug where character scale filters pointed at input_idx = i + 2
    assert "[1:v]scale=700:-1[char0]" in result
    assert "[2:v]scale=700:-1[char1]" in result
    # PrimaryColour=black — on this white canvas, default (white fill / black
    # outline) renders as near-invisible outlined text
    assert "PrimaryColour=&H00000000" in result
    # MarginV=145, not a naive pixel value like 850 — see comment in
    # build_filter_complex for why: the subtitles filter scales MarginV by
    # ~6.7x relative to canvas height for plain .srt input with no PlayRes
    assert "MarginV=145" in result


def test_build_filter_complex_empty_cues():
    result = compose.build_filter_complex([], "output/narration/ep01.srt")
    assert "subtitles=" in result
