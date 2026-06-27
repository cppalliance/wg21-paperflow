#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from whisker.golden import (
    GoldenItem,
    diff_goldens,
    normalize_for_exact_lane,
)


def _item(pid, candidate, expected, expected_failure=False):
    return GoldenItem(pid=pid, candidate=candidate, expected=expected,
                      expected_failure=expected_failure)


# -- normalizer --------------------------------------------------------------


def test_normalize_collapses_crlf_and_trailing_ws():
    assert normalize_for_exact_lane("a  \r\nb\t\r\n") == "a\nb\n"


def test_normalize_single_trailing_newline():
    assert normalize_for_exact_lane("x\n\n\n") == "x\n"
    assert normalize_for_exact_lane("x") == "x\n"


def test_normalize_empty_is_empty():
    assert normalize_for_exact_lane("") == ""
    assert normalize_for_exact_lane("\n\n") == ""


# -- diff_goldens ------------------------------------------------------------


def test_identical_after_normalization_is_ok():
    # CRLF vs LF + trailing space differences are normalized away -> stable.
    report = diff_goldens([_item("P1", "# T\r\nbody  \r\n", "# T\nbody\n")])
    assert not report.failed
    assert report.findings[0].status == "ok"


def test_real_change_fails_with_diff():
    report = diff_goldens([_item("P1", "# T\nnew body\n", "# T\nold body\n")])
    assert report.failed
    f = report.findings[0]
    assert f.status == "changed"
    assert any("new body" in line for line in f.diff)


def test_new_paper_passes_by_default_fails_on_new():
    assert not diff_goldens([_item("P1", "x\n", None)]).failed
    strict = diff_goldens([_item("P1", "x\n", None)], fail_on_new=True)
    assert strict.failed
    assert strict.findings[0].status == "new"


def test_missing_candidate_is_hard_fail():
    report = diff_goldens([_item("P1", None, "x\n")])
    assert report.failed
    assert report.findings[0].status == "missing"


def test_expected_failure_unchanged_passes_but_is_labeled():
    report = diff_goldens([_item("P1", "x\n", "x\n", expected_failure=True)])
    assert not report.failed
    assert report.findings[0].status == "expected_failure"


def test_expected_failure_still_fails_on_any_change():
    # A known-imperfect golden must fail even on a (possibly improving) change,
    # forcing a deliberate re-bless.
    report = diff_goldens([_item("P1", "better\n", "x\n", expected_failure=True)])
    assert report.failed
    assert report.findings[0].status == "changed"


def test_report_dict_is_sorted_and_serializable():
    report = diff_goldens([_item("P2", "a\n", "a\n"), _item("P1", "b\n", "a\n")])
    d = report.to_dict()
    assert [f["pid"] for f in d["findings"]] == ["P1", "P2"]
    assert d["kind"] == "whisker-golden-report"
    assert "normalization_version" in d
    assert d["failed"] is True
