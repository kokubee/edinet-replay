"""Unit tests for the canonical JSON profile (no external assets needed)."""
from edinet_replay.canonical import CANONICAL_JSON_PROFILE, canonicalize

_PRECOMPOSED = "é"  # é
_DECOMPOSED = "é"  # e + combining acute accent


def test_profile_name_is_project_specific():
    assert CANONICAL_JSON_PROFILE == "edinet-replay-canonical-json-v1"


def test_no_whitespace_and_no_trailing_newline():
    assert canonicalize({"b": 2, "a": 1}) == b'{"a":1,"b":2}'


def test_object_keys_sorted_by_unicode_code_point():
    out = canonicalize({"a": 1, "Z": 1, "_": 1, "-": 1, ":": 1, "あ": 1, "\U0001f600": 1}).decode()

    def pos(k):
        return out.index(f'"{k}"')

    # code points: '-'=2D ':'=3A 'Z'=5A '_'=5F 'a'=61 'あ'=3042 '😀'=1F600
    assert pos("-") < pos(":") < pos("Z") < pos("_") < pos("a") < pos("あ") < pos("\U0001f600")


def test_no_unicode_normalization():
    # Precomposed é (U+00E9) and decomposed e + U+0301 must stay distinct keys.
    assert _PRECOMPOSED != _DECOMPOSED
    out = canonicalize({_PRECOMPOSED: 1, _DECOMPOSED: 2}).decode()
    assert f'"{_PRECOMPOSED}":1' in out
    assert f'"{_DECOMPOSED}":2' in out


def test_arrays_preserve_input_order():
    out = canonicalize({"n": [3, 1, 2], "s": ["C", "A", "B"]}).decode()
    assert '"n":[3,1,2]' in out
    assert '"s":["C","A","B"]' in out


def test_financial_strings_and_native_scalars():
    out = canonicalize({"value": "123456789", "nil": False, "x": None, "line": 42}).decode()
    assert '"value":"123456789"' in out  # financial value stays a string
    assert '"nil":false' in out and '"x":null' in out and '"line":42' in out


def test_deterministic_and_utf8():
    obj = {"漢字": "値", "x": [{"k": "v"}]}
    assert canonicalize(obj) == canonicalize(obj)
    assert canonicalize(obj).decode("utf-8")  # round-trips as UTF-8
