import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from importlib import import_module

narration = import_module("05_narration")


def test_build_srt_from_captions_covers_full_duration():
    captions = ["첫 문장", "둘째 문장", "셋째 문장"]
    srt = narration.build_srt_from_captions(captions, 12.0)

    assert "00:00:00,000 --> 00:00:04,000" in srt
    assert "00:00:04,000 --> 00:00:08,000" in srt
    assert "00:00:08,000 --> 00:00:12,000" in srt
    for caption in captions:
        assert caption in srt


def test_build_srt_from_captions_single_caption():
    srt = narration.build_srt_from_captions(["전체 대사"], 5.0)
    assert "00:00:00,000 --> 00:00:05,000" in srt
    assert "전체 대사" in srt
