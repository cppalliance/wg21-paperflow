#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import json
from pathlib import Path

import pytest
from paperstore.errors import MissingPaperMdError
from whisker.det.cli import (
    _golden_member_paths,
    _load_corpus_pairs,
    _load_golden_items,
    golden_main,
)
from whisker.det.golden import (
    GoldenItem,
    diff_goldens,
    normalize_for_exact_lane,
)


def _item(pid, candidate, expected, expected_failure=False):
    return GoldenItem(pid=pid, candidate=candidate, expected=expected,
                      expected_failure=expected_failure)


class _Backend:
    def __init__(self, candidates=None):
        self.candidates = candidates or {}

    def get_paper_md(self, pid):
        try:
            return self.candidates[pid]
        except KeyError:
            raise MissingPaperMdError(pid) from None


class _CorpusEntry:
    """Portable fake for case-colliding directory entries on Windows."""

    def __init__(self, name):
        self.name = name

    def is_file(self):
        return True

    def is_symlink(self):
        return False


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


def test_missing_candidate_precedes_missing_expected():
    report = diff_goldens([_item("P1", None, None)])
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


# -- CLI corpus loading ------------------------------------------------------


def test_load_golden_items_discovers_expected_only_snapshot(tmp_path):
    (tmp_path / "p2000r0.expected.md").write_text("expected\n", encoding="utf-8")

    items = _load_golden_items(
        tmp_path, _Backend({"P2000R0": "candidate\n"}), set(),
    )

    assert items == [
        GoldenItem(pid="P2000R0", candidate="candidate\n", expected="expected\n")
    ]


def test_load_golden_items_keeps_gt_only_member_new(tmp_path):
    (tmp_path / "p3000r0.gt.md").write_text("ground truth\n", encoding="utf-8")

    items = _load_golden_items(
        tmp_path, _Backend({"P3000R0": "candidate\n"}), set(),
    )

    assert items == [
        GoldenItem(pid="P3000R0", candidate="candidate\n", expected=None)
    ]
    assert diff_goldens(items).findings[0].status == "new"


def test_load_golden_items_marks_unstaged_gt_only_member_missing(tmp_path):
    (tmp_path / "p3100r0.gt.md").write_text("ground truth\n", encoding="utf-8")

    items = _load_golden_items(tmp_path, _Backend(), set())

    assert diff_goldens(items).findings[0].status == "missing"


def test_load_golden_items_deduplicates_expected_gt_pair_case_insensitively(tmp_path):
    (tmp_path / "P4000R0.expected.md").write_text("expected\n", encoding="utf-8")
    (tmp_path / "p4000r0.gt.md").write_text("ground truth\n", encoding="utf-8")
    (tmp_path / "p3000r0.gt.md").write_text("earlier ground truth\n", encoding="utf-8")

    items = _load_golden_items(
        tmp_path, _Backend({
            "P4000R0": "candidate\n",
            "P3000R0": "earlier candidate\n",
        }), set(),
    )

    assert items == [
        GoldenItem(pid="P3000R0", candidate="earlier candidate\n", expected=None),
        GoldenItem(pid="P4000R0", candidate="candidate\n", expected="expected\n")
    ]


def test_load_golden_items_resolves_actual_expected_filename_casing(tmp_path):
    expected_path = tmp_path / "p5000r0.ExPeCtEd.Md"
    expected_path.write_text("mixed-case expected\n", encoding="utf-8")

    items = _load_golden_items(
        tmp_path, _Backend({"P5000R0": "candidate\n"}), set(),
    )

    assert items[0].expected == "mixed-case expected\n"


def test_member_paths_reject_duplicate_expected_snapshots_without_paths(
    tmp_path, monkeypatch,
):
    entries = [
        _CorpusEntry("P5100R0.expected.md"),
        _CorpusEntry("p5100r0.ExPeCtEd.Md"),
    ]
    monkeypatch.setattr(Path, "iterdir", lambda self: iter(entries))

    with pytest.raises(ValueError) as caught:
        _golden_member_paths(tmp_path)
    message = str(caught.value)
    assert "P5100R0.expected.md" in message
    assert "p5100r0.ExPeCtEd.Md" in message
    assert str(tmp_path) not in message


def test_member_paths_reject_duplicate_gt_markers_without_paths(
    tmp_path, monkeypatch,
):
    entries = [
        _CorpusEntry("P5200R0.gt.md"),
        _CorpusEntry("p5200r0.GT.MD"),
    ]
    monkeypatch.setattr(Path, "iterdir", lambda self: iter(entries))

    with pytest.raises(ValueError) as caught:
        _golden_member_paths(tmp_path)
    message = str(caught.value)
    assert "P5200R0.gt.md" in message
    assert "p5200r0.GT.MD" in message
    assert str(tmp_path) not in message


def test_golden_controls_membership_validation_error(
    tmp_path, monkeypatch, caplog,
):
    monkeypatch.setattr(
        "whisker.det.cli.open_backend", lambda workspace: _Backend(),
    )
    monkeypatch.setattr(
        "whisker.det.cli._golden_member_paths",
        lambda corpus: (_ for _ in ()).throw(
            ValueError("ambiguous members: P5200R0.gt.md, p5200r0.GT.MD")
        ),
    )

    try:
        rc = golden_main(["--corpus", str(tmp_path)])
    except ValueError:
        pytest.fail("membership validation error escaped golden_main")
    assert rc == 1
    assert "P5200R0.gt.md" in caplog.text
    assert "p5200r0.GT.MD" in caplog.text
    assert str(tmp_path) not in caplog.text


def test_golden_update_rejects_symlinked_member_before_write(
    tmp_path, monkeypatch, caplog,
):
    expected_path = tmp_path / "P5300R0.expected.md"
    expected_path.write_text("outside sentinel\n", encoding="utf-8")
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda self: self == expected_path or original_is_symlink(self),
    )
    monkeypatch.setattr(
        "whisker.det.cli.open_backend",
        lambda workspace: _Backend({"P5300R0": "replacement\n"}),
    )

    assert golden_main(["--corpus", str(tmp_path), "--update"]) == 1
    assert "P5300R0.expected.md" in caplog.text
    assert str(tmp_path) not in caplog.text
    assert expected_path.read_text(encoding="utf-8") == "outside sentinel\n"


def test_manifest_expected_failures_cover_expected_only_mixed_case_members(
    tmp_path, monkeypatch, capsys,
):
    (tmp_path / "P5400R0.expected.md").write_text("first\n", encoding="utf-8")
    (tmp_path / "p5500r0.ExPeCtEd.Md").write_text("second\n", encoding="utf-8")
    (tmp_path / "golden.json").write_text(
        json.dumps({
            "kind": "whisker-golden-manifest",
            "expected_failures": ["p5400r0", "P5500r0"],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "whisker.det.cli.open_backend",
        lambda workspace: _Backend({
            "P5400R0": "first\n",
            "P5500R0": "second\n",
        }),
    )

    assert golden_main(["--corpus", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status_counts"] == {"expected_failure": 2}
    assert [finding["pid"] for finding in payload["findings"]] == [
        "P5400R0", "P5500R0",
    ]


def test_expected_only_snapshot_with_missing_candidate_is_finding(tmp_path):
    (tmp_path / "P6000R0.expected.md").write_text("expected\n", encoding="utf-8")

    items = _load_golden_items(tmp_path, _Backend(), set())
    report = diff_goldens(items)

    assert len(report.findings) == 1
    assert report.findings[0].status == "missing"
    assert report.failed


def test_golden_empty_corpus_still_errors(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(
        "whisker.det.cli.open_backend", lambda workspace: _Backend(),
    )

    assert golden_main(["--corpus", str(tmp_path)]) == 1
    assert "no " in caplog.text and "found" in caplog.text


def test_golden_update_rewrites_existing_expected_member_in_place(
    tmp_path, monkeypatch,
):
    expected_path = tmp_path / "p7000r0.expected.md"
    expected_path.write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(
        "whisker.det.cli.open_backend",
        lambda workspace: _Backend({"P7000R0": "new  \r\n"}),
    )

    assert golden_main(["--corpus", str(tmp_path), "--update"]) == 0
    assert expected_path.read_text(encoding="utf-8") == "new\n"
    assert list(tmp_path.iterdir()) == [expected_path]


def test_golden_gt_only_member_preserves_fail_on_new(
    tmp_path, monkeypatch, capsys,
):
    (tmp_path / "p7500r0.gt.md").write_text("ground truth\n", encoding="utf-8")
    monkeypatch.setattr(
        "whisker.det.cli.open_backend",
        lambda workspace: _Backend({"P7500R0": "candidate\n"}),
    )

    rc = golden_main([
        "--corpus", str(tmp_path), "--fail-on-new", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 5
    assert payload["status_counts"] == {"new": 1}


def test_golden_update_bootstraps_gt_only_member(tmp_path, monkeypatch):
    gt_path = tmp_path / "p7600r0.gt.md"
    gt_path.write_text("ground truth\n", encoding="utf-8")
    monkeypatch.setattr(
        "whisker.det.cli.open_backend",
        lambda workspace: _Backend({"P7600R0": "candidate  \r\n"}),
    )

    assert golden_main(["--corpus", str(tmp_path), "--update"]) == 0
    expected_path = tmp_path / "P7600R0.expected.md"
    assert expected_path.read_text(encoding="utf-8") == "candidate\n"
    assert gt_path.read_text(encoding="utf-8") == "ground truth\n"


def test_lane2_loader_membership_remains_gt_only(tmp_path):
    (tmp_path / "P8000R0.expected.md").write_text("expected\n", encoding="utf-8")
    (tmp_path / "P9000R0.gt.md").write_text("ground truth\n", encoding="utf-8")
    backend = _Backend({
        "P8000R0": "expected-only candidate\n",
        "P9000R0": "gt candidate\n",
    })

    assert _load_corpus_pairs(tmp_path, backend) == [
        ("P9000R0", "gt candidate\n", "ground truth\n")
    ]
