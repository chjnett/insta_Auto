import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from importlib import import_module

script_gen = import_module("02_script_gen")


def test_build_expression_cues_covers_full_duration():
    expression_cues = script_gen.build_expression_cues(29.0)
    last_expr = expression_cues[-1]
    assert round(last_expr["start"] + last_expr["duration"], 1) == 29.0


def test_build_expression_cues_poses_are_valid():
    valid_poses = {"base", "surprised", "nodding", "pointing", "questioning", "celebrating"}
    expression_cues = script_gen.build_expression_cues(20.0)
    assert all(c["pose"] in valid_poses for c in expression_cues)


def test_build_props_cues_from_segments_matches_captions_exactly():
    # each props set must show for exactly the real measured duration of
    # the caption it depicts — not an independent generic split, which is
    # how icons ended up mismatched with what was actually being said
    segments = [
        {"caption": "첫 문장", "start": 0.0, "duration": 3.2},
        {"caption": "둘째 문장", "start": 3.2, "duration": 5.1},
        {"caption": "셋째 문장", "start": 8.3, "duration": 2.7},
    ]
    props_cues = script_gen.build_props_cues_from_segments(segments)

    assert len(props_cues) == len(segments)
    assert [c["index"] for c in props_cues] == [0, 1, 2]
    for cue, seg in zip(props_cues, segments):
        assert cue["start"] == seg["start"]
        assert cue["duration"] == seg["duration"]
