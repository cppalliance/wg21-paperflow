#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import json
import sys
from pathlib import Path

import pytest

_CALIBRATION_DIR = Path(__file__).resolve().parent
if str(_CALIBRATION_DIR) not in sys.path:
    sys.path.insert(0, str(_CALIBRATION_DIR))

from calibration_sampler import (  # noqa: E402
    ScoredPaper,
    build_blind_worksheet,
    sample_calibration_candidates,
)


def _paper(pid, verdict, unigram_coverage=0.9):
    return ScoredPaper(pid=pid, verdict=verdict, unigram_coverage=unigram_coverage)


def _mixed_papers():
    """5 pass, 3 review, 2 fail: an uneven, realistic-shaped fleet."""
    papers = []
    for i in range(5):
        papers.append(_paper(f"pass{i}", "pass", unigram_coverage=0.96 + i * 0.001))
    for i in range(3):
        papers.append(_paper(f"review{i}", "review", unigram_coverage=0.90 + i * 0.001))
    for i in range(2):
        papers.append(_paper(f"fail{i}", "fail", unigram_coverage=0.5 + i * 0.001))
    return papers


# -- Stratification -----------------------------------------------------


def test_stratification_counts_match_min_n_per_band_and_band_size():
    papers = _mixed_papers()
    result = sample_calibration_candidates(papers, n_per_band=2, seed=1)

    by_verdict = {band.verdict: band for band in result.bands}
    assert by_verdict["pass"].available == 5
    assert by_verdict["pass"].drawn == min(2, 5)
    assert by_verdict["review"].available == 3
    assert by_verdict["review"].drawn == min(2, 3)
    assert by_verdict["fail"].available == 2
    assert by_verdict["fail"].drawn == min(2, 2)

    # Each band sampled independently: candidates drawn from a band are a
    # subset of that band's own pids, never mixed with another band's pids.
    drawn_pass = {p.pid for p in result.candidates if p.verdict == "pass"}
    drawn_review = {p.pid for p in result.candidates if p.verdict == "review"}
    drawn_fail = {p.pid for p in result.candidates if p.verdict == "fail"}
    assert drawn_pass <= {f"pass{i}" for i in range(5)}
    assert drawn_review <= {f"review{i}" for i in range(3)}
    assert drawn_fail <= {f"fail{i}" for i in range(2)}
    assert len(drawn_pass) == 2
    assert len(drawn_review) == 2
    assert len(drawn_fail) == 2


def test_total_candidates_equals_sum_of_band_draws():
    papers = _mixed_papers()
    result = sample_calibration_candidates(papers, n_per_band=2, seed=7)
    assert len(result.candidates) == sum(band.drawn for band in result.bands)


# -- Determinism ----------------------------------------------------------


def test_same_seed_same_input_gives_identical_output():
    papers = _mixed_papers()
    result_a = sample_calibration_candidates(papers, n_per_band=3, seed=42)
    result_b = sample_calibration_candidates(papers, n_per_band=3, seed=42)

    pids_a = [p.pid for p in result_a.candidates]
    pids_b = [p.pid for p in result_b.candidates]
    assert pids_a == pids_b
    # Full identity, not just pid: same objects' field values throughout.
    assert result_a.candidates == result_b.candidates


def test_same_seed_is_independent_of_input_list_object_identity():
    """A fresh but value-equal input list (not the same Python list object)
    must still reproduce the identical output: determinism is a property of
    (seed, input values), not of incidental list identity or construction
    order.
    """
    papers_a = _mixed_papers()
    papers_b = list(_mixed_papers())  # separate ScoredPaper instances, same values
    result_a = sample_calibration_candidates(papers_a, n_per_band=3, seed=42)
    result_b = sample_calibration_candidates(papers_b, n_per_band=3, seed=42)
    assert result_a.candidates == result_b.candidates


def test_different_seeds_yield_different_order():
    """Determinism (reproducibility for one seed) is the property under
    test elsewhere; here we only need ONE seed pair that is known to diverge,
    to prove the seed is actually load-bearing and not silently ignored.
    Seeds 1 and 2 were confirmed (by running this suite) to produce different
    permutations of the 5-paper "pass" band below; if a future refactor to
    the shuffling strategy breaks that, this test's job is exactly to catch
    it, so it should NOT be treated as flaky and loosened without checking
    whether the seed became inert.
    """
    papers = _mixed_papers()
    result_1 = sample_calibration_candidates(papers, n_per_band=5, seed=1)
    result_2 = sample_calibration_candidates(papers, n_per_band=5, seed=2)

    order_1 = [p.pid for p in result_1.candidates if p.verdict == "pass"]
    order_2 = [p.pid for p in result_2.candidates if p.verdict == "pass"]
    assert order_1 != order_2


# -- Disjointness -----------------------------------------------------------


def test_no_paper_sampled_twice_across_bands():
    papers = _mixed_papers()
    result = sample_calibration_candidates(papers, n_per_band=10, seed=3)
    pids = [p.pid for p in result.candidates]
    assert len(pids) == len(set(pids))


def test_disjointness_invariant_holds_even_with_full_bands():
    # n_per_band larger than every band forces every paper to be drawn;
    # disjointness must still hold (each pid appears exactly once overall).
    papers = _mixed_papers()
    result = sample_calibration_candidates(papers, n_per_band=100, seed=9)
    assert len(result.candidates) == len(papers)
    assert {p.pid for p in result.candidates} == {p.pid for p in papers}


# -- Shortfall handling -------------------------------------------------


def test_shortfall_band_yields_all_available_not_an_error():
    papers = _mixed_papers()  # fail band has only 2 papers
    result = sample_calibration_candidates(papers, n_per_band=10, seed=5)

    fail_band = next(band for band in result.bands if band.verdict == "fail")
    assert fail_band.available == 2
    assert fail_band.requested == 10
    assert fail_band.drawn == 2
    assert fail_band.shortfall == 8

    drawn_fail_pids = {p.pid for p in result.candidates if p.verdict == "fail"}
    assert drawn_fail_pids == {"fail0", "fail1"}


def test_empty_band_yields_zero_drawn_not_an_error():
    papers = [_paper("onlypass", "pass")]
    result = sample_calibration_candidates(papers, n_per_band=5, seed=5)

    review_band = next(band for band in result.bands if band.verdict == "review")
    fail_band = next(band for band in result.bands if band.verdict == "fail")
    assert review_band.available == 0
    assert review_band.drawn == 0
    assert review_band.shortfall == 5
    assert fail_band.available == 0
    assert fail_band.drawn == 0


def test_unknown_verdict_raises_value_error():
    papers = [_paper("bad", "maybe")]
    with pytest.raises(ValueError):
        sample_calibration_candidates(papers, n_per_band=1, seed=1)


def test_negative_n_per_band_raises_value_error():
    with pytest.raises(ValueError):
        sample_calibration_candidates(_mixed_papers(), n_per_band=-1, seed=1)


# -- Blind worksheet: leak test (the most important test in this module) ---


def test_blind_worksheet_never_leaks_verdict_or_unigram_coverage():
    """Airtight leak test: plant a sentinel unigram_coverage value and a
    distinctive verdict on the input, then assert NEITHER survives into the
    worksheet: not as a dict key, not as a value anywhere (including nested
    structures), and not in the JSON-serialized form of every entry (which
    would also catch a leak smuggled into a string field).
    """
    poisoned_value = 0.1234
    poisoned_verdict = "fail"
    candidates = [
        ScoredPaper(pid="p1234r5", verdict=poisoned_verdict, unigram_coverage=poisoned_value),
        ScoredPaper(pid="p6789r0", verdict="pass", unigram_coverage=0.9999),
    ]
    markdown_lookup = {
        "p1234r5": "# Some Paper\n\nBody text.",
        "p6789r0": "# Another Paper\n\nMore body text.",
    }

    worksheet = build_blind_worksheet(candidates, markdown_lookup)

    assert len(worksheet) == 2
    for entry in worksheet:
        # Key-level leak check.
        assert "verdict" not in entry
        assert "unigram_coverage" not in entry

        # Value-level leak check: the poisoned float must not appear
        # anywhere in the entry's values, top-level or nested.
        assert poisoned_value not in entry.values()
        for value in entry.values():
            if isinstance(value, (list, dict)):
                assert str(poisoned_value) not in json.dumps(value)

        # Serialized-form leak check: dump the WHOLE entry to JSON and
        # confirm the poisoned float's string form never appears, catching
        # anything that might sneak in via string interpolation. Match the
        # JSON key form exactly (`"verdict":`) rather than a bare substring,
        # since the legitimate `human_verdict` key contains "verdict" too.
        serialized = json.dumps(entry)
        assert str(poisoned_value) not in serialized
        assert '"verdict":' not in serialized
        assert '"unigram_coverage":' not in serialized


def test_blind_worksheet_leak_test_would_actually_catch_a_leak():
    """Negative control for the leak test above: prove the assertions are
    not vacuously true by constructing a deliberately-leaky dict (as if a
    future edit reintroduced ``**vars(paper)``) and confirming the same
    assertions WOULD fail against it. This guards against the leak test
    itself being broken in a way that always passes.
    """
    poisoned_value = 0.1234
    leaky_entry = {
        "pid": "p1234r5",
        "verdict": "fail",
        "unigram_coverage": poisoned_value,
        "markdown": "# Some Paper",
    }
    with pytest.raises(AssertionError):
        assert "verdict" not in leaky_entry
    with pytest.raises(AssertionError):
        assert "unigram_coverage" not in leaky_entry
    with pytest.raises(AssertionError):
        assert poisoned_value not in leaky_entry.values()
    with pytest.raises(AssertionError):
        assert str(poisoned_value) not in json.dumps(leaky_entry)


# -- Schema shape ------------------------------------------------------------


def test_worksheet_entry_has_expected_keys_with_none_in_judgment_fields():
    candidates = [ScoredPaper(pid="p1000r0", verdict="review", unigram_coverage=0.91)]
    markdown_lookup = {"p1000r0": "# Title\n\nBody."}

    worksheet = build_blind_worksheet(candidates, markdown_lookup)
    assert len(worksheet) == 1
    entry = worksheet[0]

    expected_keys = {
        "pid", "pr", "source_type", "markdown",
        "human_verdict", "label", "defect_groups", "split",
    }
    assert set(entry.keys()) == expected_keys

    assert entry["pid"] == "p1000r0"
    assert entry["markdown"] == "# Title\n\nBody."
    for judgment_field in ("pr", "source_type", "human_verdict", "label", "split"):
        assert entry[judgment_field] is None
    assert entry["defect_groups"] == []


def test_worksheet_preserves_candidate_order_and_full_markdown_text():
    candidates = [
        ScoredPaper(pid="a", verdict="pass", unigram_coverage=0.99),
        ScoredPaper(pid="b", verdict="fail", unigram_coverage=0.4),
    ]
    long_markdown = "line\n" * 5000
    markdown_lookup = {"a": "short", "b": long_markdown}

    worksheet = build_blind_worksheet(candidates, markdown_lookup)
    assert [entry["pid"] for entry in worksheet] == ["a", "b"]
    assert worksheet[0]["markdown"] == "short"
    assert worksheet[1]["markdown"] == long_markdown


def test_worksheet_raises_key_error_for_missing_markdown():
    candidates = [ScoredPaper(pid="missing", verdict="pass", unigram_coverage=0.9)]
    with pytest.raises(KeyError):
        build_blind_worksheet(candidates, {})
