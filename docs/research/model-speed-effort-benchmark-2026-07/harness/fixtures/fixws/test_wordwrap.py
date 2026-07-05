import pytest
from wordwrap import wrap


def test_basic():
    assert wrap("the quick brown fox", 10) == ["the quick", "brown fox"]


def test_exact_fit():
    # "aa bb" is exactly 5 chars and must fit on one line of width 5
    assert wrap("aa bb", 5) == ["aa bb"]


def test_no_overlong_lines():
    lines = wrap("one two three four five six seven", 9)
    assert all(len(line) <= 9 for line in lines)


def test_long_word_broken():
    assert wrap("abcdefghij", 4) == ["abcd", "efgh", "ij"]


def test_long_word_flows_with_others():
    assert wrap("hi abcdefgh yo", 4) == ["hi", "abcd", "efgh", "yo"]


def test_empty():
    assert wrap("", 5) == []


def test_whitespace_only():
    assert wrap("   \n\t ", 5) == []


def test_word_equal_width():
    assert wrap("abcde", 5) == ["abcde"]


def test_reconstruction():
    text = "pack my box with five dozen liquor jugs"
    lines = wrap(text, 11)
    assert " ".join(lines).split() == text.split()


def test_width_zero_raises():
    with pytest.raises(ValueError):
        wrap("hello", 0)
