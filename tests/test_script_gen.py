import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from importlib import import_module

script_gen = import_module("02_script_gen")


def test_build_cues_props_cycle_through_all_generated_sets():
    expression_cues, props_cues = script_gen.build_cues(29.0)

    # default is 4 generated props sets — must cycle through all of them,
    # not just alternate between 2
    assert len(props_cues) > 4
    assert [c["index"] for c in props_cues[:6]] == [0, 1, 2, 3, 0, 1]

    # cues must fully cover the real duration with no gaps at the end
    assert props_cues[-1]["start"] + props_cues[-1]["duration"] == round(29.0, 2)
    last_expr = expression_cues[-1]
    assert round(last_expr["start"] + last_expr["duration"], 1) == 29.0


def test_build_cues_respects_custom_props_set_count():
    _, props_cues = script_gen.build_cues(29.0, n_props_sets=2)
    assert [c["index"] for c in props_cues[:4]] == [0, 1, 0, 1]


def test_build_cues_expression_poses_are_valid():
    valid_poses = {"base", "surprised", "nodding", "pointing", "questioning", "celebrating"}
    expression_cues, _ = script_gen.build_cues(20.0)
    assert all(c["pose"] in valid_poses for c in expression_cues)
