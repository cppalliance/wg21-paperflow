"""Tests for lib.similarity."""

from tomd.lib.similarity import _MAX_COMPARE_LENGTH, similar, word_jaccard


def test_similar_identical():
    assert similar("hello world", "hello world")


def test_similar_minor_difference():
    assert similar("hello world", "hello worlds")


def test_similar_unrelated():
    assert not similar("hello world", "xyzzy foobar quux")


def test_similar_empty_strings():
    assert similar("", "")


def test_similar_one_empty():
    assert not similar("hello", "")


def test_similar_circuit_breaker():
    assert not similar("a" * (_MAX_COMPARE_LENGTH + 1), "b" * (_MAX_COMPARE_LENGTH + 1))


def test_similar_long_identical():
    assert similar("a" * (_MAX_COMPARE_LENGTH + 50), "a" * (_MAX_COMPARE_LENGTH + 50))


def test_similar_short_identical():
    assert similar("test", "test")


def test_similar_disjoint_words():
    assert not similar("aaa bbb", "ccc ddd")


def test_word_jaccard_identical_is_one():
    assert word_jaccard("alpha beta gamma", "alpha beta gamma") == 1.0


def test_word_jaccard_disjoint_is_zero():
    assert word_jaccard("alpha beta", "gamma delta") == 0.0


def test_word_jaccard_both_empty_is_one():
    assert word_jaccard("", "") == 1.0


def test_word_jaccard_one_empty_is_zero():
    assert word_jaccard("alpha", "") == 0.0


def test_word_jaccard_partial_overlap():
    # {a,b} vs {a,b,c} -> 2/3
    assert abs(word_jaccard("a b", "a b c") - (2 / 3)) < 1e-9
