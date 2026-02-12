import json
from pathlib import Path

import pytest

from worker.normalization import normalize_strict, normalize_soft


VECTORS_PATH = Path(__file__).resolve().parent.parent / "test_vectors" / "normalization_test_vectors.json"


def _load_vectors():
    with VECTORS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Basic schema validation for determinism & nicer failures
    seen = set()
    for v in data:
        assert "case_id" in v and isinstance(v["case_id"], str)
        assert v["case_id"] not in seen, f"Duplicate case_id: {v['case_id']}"
        seen.add(v["case_id"])
        for k in ("input_text", "expected_strict", "expected_soft", "notes"):
            assert k in v, f"Missing key {k} in {v['case_id']}"
    return data


@pytest.mark.parametrize("vec", _load_vectors(), ids=lambda v: v["case_id"])
def test_normalize_strict_and_soft(vec):
    inp = vec["input_text"]
    exp_strict = vec["expected_strict"]
    exp_soft = vec["expected_soft"]

    got_strict = normalize_strict(inp)
    got_soft = normalize_soft(inp)

    assert got_strict == exp_strict
    assert got_soft == exp_soft


def test_none_input_is_empty_string():
    assert normalize_strict(None) == ""
    assert normalize_soft(None) == ""
