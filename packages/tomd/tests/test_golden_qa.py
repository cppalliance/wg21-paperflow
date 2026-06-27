"""Tests for the golden QA orchestration helpers."""

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tomd.lib.golden_qa import (
    bless_stem,
    build_review_prompt,
    download_source,
    fidelity_verdict,
    find_source,
    generate_ideal,
    is_unedited_seed,
    issue_for_stem,
    rebless_stems,
    render_pdf_pages,
    review_ideal,
    score_report,
    score_result,
    score_stem,
    stage_source,
    tomd_markdown,
    validate_anchors_json,
    validate_facts_jsonl,
)

_GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden"
_SRC = _GOLDEN / "sources"
_IDEALS = _GOLDEN / "ideals"

# The p4228r0 HTML source ships with the fixtures, but a partial clone may lack
# it; skip (do not fail) when absent, matching test_html_golden.py.
requires_source = pytest.mark.skipif(
    not (_SRC / "p4228r0.html").is_file(),
    reason="sources/p4228r0.html not staged",
)


def _stage(tmp_path: Path, ideal_text: str | None = None) -> Path:
    """Stage p4228r0's source + ideal into a temp golden root (subdir layout).

    With `ideal_text` the ideal is that stub; otherwise the real blessed ideal is
    copied. Returns the temp manifest path.
    """
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "ideals").mkdir(exist_ok=True)
    shutil.copy(_SRC / "p4228r0.html", tmp_path / "sources" / "p4228r0.html")
    if ideal_text is None:
        shutil.copy(_IDEALS / "p4228r0.md", tmp_path / "ideals" / "p4228r0.md")
    else:
        (tmp_path / "ideals" / "p4228r0.md").write_text(ideal_text, encoding="utf-8")
    return tmp_path / "baselines.json"


@requires_source
def test_find_source_html():
    src = find_source("p4228r0", _GOLDEN)
    assert src is not None and src.suffix == ".html"


def test_find_source_missing_returns_none():
    assert find_source("does-not-exist", _GOLDEN) is None


@requires_source
def test_tomd_markdown_html_nonempty():
    md = tomd_markdown("p4228r0", _GOLDEN)
    assert md and "Revision History" in md


@requires_source
def test_score_stem_matches_committed_baseline():
    # p4228r0 has a blessed ideal; its score must reproduce the manifest.
    # heading is 2/3 under the graded axis: text and nesting are correct, only
    # the absolute level is uniformly wrong (the #155 signature).
    scores = score_stem("p4228r0", _GOLDEN)
    assert scores["heading"] == pytest.approx(round(2 / 3, 2))  # 2/3 rounds to 0.67
    assert scores["frontmatter"] == 1.0
    assert scores["text"] == pytest.approx(0.85)


@requires_source
def test_issue_for_stem_p4228r0_drafts_heading_issue():
    drafts = issue_for_stem("p4228r0", _GOLDEN)
    assert drafts
    assert any("heading" in d.lower() for d in drafts)


@requires_source
def test_score_report_has_deltas_and_heading_subsignals():
    rows = score_report("p4228r0", _GOLDEN, _GOLDEN / "baselines.json")
    by_axis = {r.axis: r for r in rows}
    assert by_axis["heading"].baseline is not None
    assert by_axis["heading"].delta == pytest.approx(
        by_axis["heading"].current - by_axis["heading"].baseline)
    assert "level" in by_axis["heading"].sub


@requires_source
def test_fidelity_verdict_passes_faithful_ideal():
    ideal = (_IDEALS / "p4228r0.md").read_text(encoding="utf-8")
    v = fidelity_verdict(_SRC / "p4228r0.html", ideal)
    assert v.ok
    assert 0.80 < v.coverage < 0.90


@requires_source
def test_fidelity_verdict_rejects_gutted_candidate():
    # A candidate that dropped almost all content must fail.
    gutted = "---\ntitle: x\n---\n\n## Only heading, no body.\n"
    v = fidelity_verdict(_SRC / "p4228r0.html", gutted)
    assert not v.ok
    assert v.reason  # human-readable


@requires_source
def test_bless_stem_writes_exact_baseline(tmp_path):
    manifest = _stage(tmp_path)
    manifest.write_text("{}\n", encoding="utf-8")
    row = bless_stem("p4228r0", tmp_path, manifest)
    assert row["heading"] == pytest.approx(round(2 / 3, 2))  # 2/3 rounds to 0.67
    written = json.loads(manifest.read_text(encoding="utf-8"))
    assert written["p4228r0"]["heading"] == pytest.approx(round(2 / 3, 2))


@requires_source
def test_bless_stem_rejects_unfaithful(tmp_path):
    manifest = _stage(tmp_path, ideal_text="---\ntitle: x\n---\n\n## stub\n")
    manifest.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="fidelity"):
        bless_stem("p4228r0", tmp_path, manifest)
    assert json.loads(manifest.read_text(encoding="utf-8")) == {}


@requires_source
def test_rebless_refuses_to_lower_baseline_without_force(tmp_path):
    manifest = _stage(tmp_path)
    # baseline higher than tomd can currently reach -> rebless would lower it.
    manifest.write_text(json.dumps({"p4228r0": {"heading": 1.0}}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="lower"):
        rebless_stems(["p4228r0"], tmp_path, manifest, force=False)
    # the manifest is left untouched on refusal.
    assert json.loads(manifest.read_text(encoding="utf-8"))["p4228r0"]["heading"] == 1.0


@requires_source
def test_rebless_force_lowers_baseline(tmp_path):
    manifest = _stage(tmp_path)
    manifest.write_text(json.dumps({"p4228r0": {"heading": 1.0}}) + "\n", encoding="utf-8")
    rebless_stems(["p4228r0"], tmp_path, manifest, force=True)
    written = json.loads(manifest.read_text(encoding="utf-8"))
    assert written["p4228r0"]["heading"] == pytest.approx(round(2 / 3, 2))


@requires_source
def test_rebless_raises_baseline_up(tmp_path):
    manifest = _stage(tmp_path)
    manifest.write_text(json.dumps({"p4228r0": {"heading": 0.0}}) + "\n", encoding="utf-8")
    outcomes = rebless_stems(["p4228r0"], tmp_path, manifest, force=False)
    written = json.loads(manifest.read_text(encoding="utf-8"))
    assert written["p4228r0"]["heading"] == pytest.approx(round(2 / 3, 2))
    assert outcomes[0].stem == "p4228r0"


def test_render_pdf_pages_writes_one_png_per_page(tmp_path):
    pdf = _SRC / "p3714r0.pdf"
    if not pdf.is_file():
        pytest.skip("missing pdf fixture sources/p3714r0.pdf")
    pages = render_pdf_pages(pdf, tmp_path)
    assert pages
    assert all(p.suffix == ".png" and p.is_file() for p in pages)


def test_stage_source_copies_into_sources(tmp_path):
    src = tmp_path / "src.html"
    src.write_text("<html></html>", encoding="utf-8")
    dest = stage_source("p9999r0", src, tmp_path)
    assert dest == tmp_path / "sources" / "p9999r0.html"
    assert dest.read_text(encoding="utf-8") == "<html></html>"


def test_stage_source_rejects_unknown_suffix(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        stage_source("p9999r0", src, tmp_path)


def test_download_source_detects_pdf(tmp_path):
    def fake_opener(url):
        assert url == "https://wg21.link/p1r0"
        return ("https://www.open-std.org/.../p1r0.pdf", b"%PDF-1.7\nbody")
    dest = download_source("p1r0", tmp_path, opener=fake_opener)
    assert dest == tmp_path / "sources" / "p1r0.pdf"
    assert dest.read_bytes().startswith(b"%PDF")


def test_download_source_detects_html(tmp_path):
    def fake_opener(url):
        return ("https://example.com/p1r0", b"<!DOCTYPE html><html></html>")
    dest = download_source("p1r0", tmp_path, opener=fake_opener)
    assert dest == tmp_path / "sources" / "p1r0.html"


def test_generate_ideal_seeds_from_tomd(tmp_path):
    # generate writes tomd's OWN conversion as the starting draft: no LLM, and
    # byte-identical to tomd_markdown so the uncorrected seed scores a perfect
    # match (the human then edits structure toward the source to open the gap).
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "p9999r0.html").write_text(
        "<html><body><h1>Title</h1><p>Body text.</p></body></html>",
        encoding="utf-8")
    dest = generate_ideal("p9999r0", tmp_path)
    assert dest == tmp_path / "ideals" / "p9999r0.md"
    assert dest.read_text(encoding="utf-8") == tomd_markdown("p9999r0", tmp_path)


@requires_source
def test_generate_seeded_ideal_scores_perfect(tmp_path):
    # The behavioral contract of the seed: an uncorrected tomd seed equals tomd's
    # own output, so every axis scores 1.0 until a human corrects its structure.
    (tmp_path / "sources").mkdir()
    shutil.copy(_SRC / "p4228r0.html", tmp_path / "sources" / "p4228r0.html")
    generate_ideal("p4228r0", tmp_path)
    scores = score_stem("p4228r0", tmp_path)
    assert all(v == pytest.approx(1.0) for v in scores.values())


def test_is_unedited_seed_detects_raw_seed(tmp_path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "p9999r0.html").write_text(
        "<html><body><h1>Title</h1><p>Body.</p></body></html>", encoding="utf-8")
    generate_ideal("p9999r0", tmp_path)  # raw seed == tomd's own output
    assert is_unedited_seed("p9999r0", tmp_path) is True
    ip = tmp_path / "ideals" / "p9999r0.md"
    ip.write_text(ip.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
    assert is_unedited_seed("p9999r0", tmp_path) is False


@requires_source
def test_bless_stem_rejects_unedited_seed(tmp_path):
    # Seeding then blessing without correcting must fail: a raw seed is byte-
    # identical to tomd's output, so it would test nothing.
    (tmp_path / "sources").mkdir()
    shutil.copy(_SRC / "p4228r0.html", tmp_path / "sources" / "p4228r0.html")
    generate_ideal("p4228r0", tmp_path)
    manifest = tmp_path / "baselines.json"
    manifest.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="seed"):
        bless_stem("p4228r0", tmp_path, manifest)
    assert json.loads(manifest.read_text(encoding="utf-8")) == {}


def test_review_ideal_passes_source_and_draft_to_runner(tmp_path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "p9999r0.html").write_text(
        "<html><body><h1>Title</h1></body></html>", encoding="utf-8")
    (tmp_path / "ideals").mkdir()
    (tmp_path / "ideals" / "p9999r0.md").write_text("## Title\n", encoding="utf-8")
    captured = {}

    def fake_runner(prompt, golden_dir):
        captured["prompt"] = prompt
        return "- heading level wrong at §1\n"

    out = review_ideal("p9999r0", tmp_path, runner=fake_runner)
    assert out == "- heading level wrong at §1\n"
    # The prompt names the paper and embeds the candidate draft under review.
    assert "P9999R0" in captured["prompt"]
    assert "## Title" in captured["prompt"]


def test_build_review_prompt_embeds_skill_text(tmp_path):
    src = tmp_path / "p9999r0.html"
    src.write_text("<html></html>", encoding="utf-8")
    prompt = build_review_prompt(
        "p9999r0", src, tmp_path, "## candidate\n",
        skill_text="CANONICAL-CONTRACT-RULES")
    assert "CANONICAL-CONTRACT-RULES" in prompt  # the shared skill is the contract
    assert "## candidate" in prompt
    assert "P9999R0" in prompt


@requires_source
def test_review_ideal_embeds_committed_skill_contract():
    # The command reads the committed tomd-review SKILL.md and embeds it, so the
    # command and interactive use share one contract.
    captured = {}

    def fake_runner(prompt, golden_dir):
        captured["prompt"] = prompt
        return ""

    review_ideal("p4228r0", _GOLDEN, runner=fake_runner)
    assert "# tomd Review" in captured["prompt"]  # the committed SKILL.md heading


def test_review_ideal_requires_source(tmp_path):
    (tmp_path / "ideals").mkdir()
    (tmp_path / "ideals" / "p9999r0.md").write_text("## x\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="source"):
        review_ideal("p9999r0", tmp_path, runner=lambda *a: "")


def test_review_ideal_requires_candidate(tmp_path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "p9999r0.html").write_text("<html></html>", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="candidate"):
        review_ideal("p9999r0", tmp_path, runner=lambda *a: "")


# --- Task 2: whisker gate tests ---

_GATE_PASS_RESPONSE = {
    "pid": "p4228r0",
    "verdict": "pass",
    "hard_flags": [],
    "soft_flags": [],
    "gates": [
        {"name": "front_matter_valid", "passed": True, "detail": ""},
        {"name": "non_empty", "passed": True, "detail": ""},
        {"name": "heading_monotone", "passed": True, "detail": ""},
    ],
    "ref_nid": None, "ref_teds": None, "ref_mhs": None,
    "ref_overall": None, "content_recall": None,
    "missing_regions": [], "extra_regions": [],
}

_GATE_FAIL_RESPONSE = {
    "pid": "p4228r0",
    "verdict": "fail",
    "hard_flags": ["gate:front_matter_valid:missing keys: title"],
    "soft_flags": [],
    "gates": [
        {"name": "front_matter_valid", "passed": False,
         "detail": "missing keys: title"},
        {"name": "non_empty", "passed": True, "detail": ""},
    ],
    "ref_nid": None, "ref_teds": None, "ref_mhs": None,
    "ref_overall": None, "content_recall": None,
    "missing_regions": [], "extra_regions": [],
}


@requires_source
def test_bless_stem_rejects_failed_gate(tmp_path):
    manifest = _stage(tmp_path)
    manifest.write_text("{}\n", encoding="utf-8")
    mock_result = MagicMock()
    mock_result.returncode = 5
    mock_result.stdout = json.dumps(_GATE_FAIL_RESPONSE)
    with patch("tomd.lib.golden_qa.subprocess.run", return_value=mock_result):
        with pytest.raises(ValueError, match="structural gates"):
            bless_stem("p4228r0", tmp_path, manifest)


@requires_source
def test_bless_stem_passes_when_whisker_unavailable(tmp_path):
    manifest = _stage(tmp_path)
    manifest.write_text("{}\n", encoding="utf-8")
    mock_result = MagicMock()
    mock_result.returncode = 127
    mock_result.stdout = ""
    with patch("tomd.lib.golden_qa.subprocess.run", return_value=mock_result):
        row = bless_stem("p4228r0", tmp_path, manifest)
    assert isinstance(row, dict)


@requires_source
def test_bless_stem_passes_when_all_gates_pass(tmp_path):
    manifest = _stage(tmp_path)
    manifest.write_text("{}\n", encoding="utf-8")
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(_GATE_PASS_RESPONSE)
    with patch("tomd.lib.golden_qa.subprocess.run", return_value=mock_result):
        row = bless_stem("p4228r0", tmp_path, manifest)
    assert isinstance(row, dict)


# --- Task 3: whisker metrics panel tests ---

_WHISKER_METRICS_RESPONSE = {
    "pid": "p4228r0",
    "verdict": "pass",
    "hard_flags": [],
    "soft_flags": [],
    "gates": [],
    "ref_nid": 0.91,
    "ref_teds": 0.88,
    "ref_mhs": 0.83,
    "ref_overall": 0.8733,
    "content_recall": 0.96,
    "missing_regions": [],
    "extra_regions": [],
}


@requires_source
def test_score_result_includes_whisker_panel(tmp_path):
    from tomd.lib.golden_qa import score_result
    manifest = _stage(tmp_path)
    shutil.copy(_GOLDEN / "baselines.json", manifest)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(_WHISKER_METRICS_RESPONSE)
    with patch("tomd.lib.golden_qa.subprocess.run", return_value=mock_result):
        sr = score_result("p4228r0", tmp_path, manifest)
    assert sr.whisker is not None
    assert sr.whisker["ref_nid"] == 0.91
    assert sr.axes  # structural axes still present


@requires_source
def test_score_result_whisker_none_when_unavailable(tmp_path):
    from tomd.lib.golden_qa import score_result
    manifest = _stage(tmp_path)
    shutil.copy(_GOLDEN / "baselines.json", manifest)
    with patch("tomd.lib.golden_qa.subprocess.run", side_effect=FileNotFoundError):
        sr = score_result("p4228r0", tmp_path, manifest)
    assert sr.whisker is None
    assert sr.axes  # structural axes unaffected


@requires_source
def test_score_result_no_comprehension_without_facts(tmp_path):
    from tomd.lib.golden_qa import score_result
    manifest = _stage(tmp_path)
    shutil.copy(_GOLDEN / "baselines.json", manifest)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(_WHISKER_METRICS_RESPONSE)
    with patch("tomd.lib.golden_qa.subprocess.run", return_value=mock_result):
        sr = score_result("p4228r0", tmp_path, manifest)
    assert sr.comprehension is None


# --- Task 4: rebless whisker verdict tests ---

@requires_source
def test_rebless_includes_whisker_verdict(tmp_path):
    manifest = _stage(tmp_path)
    shutil.copy(_GOLDEN / "baselines.json", manifest)
    whisker_response = {
        "verdict": "pass", "hard_flags": [], "soft_flags": [],
        "gates": [], "ref_nid": 0.91,
    }
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(whisker_response)
    with patch("tomd.lib.golden_qa.subprocess.run", return_value=mock_result):
        outcomes = rebless_stems(["p4228r0"], tmp_path, manifest, force=True)
    assert outcomes[0].whisker_verdict == "pass"


@requires_source
def test_rebless_whisker_verdict_none_when_unavailable(tmp_path):
    manifest = _stage(tmp_path)
    shutil.copy(_GOLDEN / "baselines.json", manifest)
    with patch("tomd.lib.golden_qa.subprocess.run", side_effect=FileNotFoundError):
        outcomes = rebless_stems(["p4228r0"], tmp_path, manifest, force=True)
    assert outcomes[0].whisker_verdict is None


# --- Task 5: issue region localization tests ---

@requires_source
def test_issue_for_stem_appends_regions(tmp_path):
    """issue_for_stem appends whisker region snippets to the first draft."""
    _stage(tmp_path)
    whisker_response = {
        "verdict": "review", "hard_flags": [], "soft_flags": [],
        "gates": [],
        "missing_regions": [
            {"page": 3, "token_start": 100, "token_end": 120,
             "sample": "expected content missing here"}
        ],
        "extra_regions": [],
        "ref_nid": None, "ref_teds": None, "ref_mhs": None,
        "ref_overall": None, "content_recall": None,
    }
    mock_result = MagicMock()
    mock_result.returncode = 3
    mock_result.stdout = json.dumps(whisker_response)
    with patch("tomd.lib.golden_qa.subprocess.run", return_value=mock_result):
        drafts = issue_for_stem("p4228r0", tmp_path)
    assert any("Localized gaps" in d for d in drafts)
    assert any("expected content missing here" in d for d in drafts)


@requires_source
def test_issue_for_stem_no_regions_when_whisker_unavailable(tmp_path):
    """issue_for_stem returns normal drafts (without regions) when whisker fails."""
    _stage(tmp_path)
    with patch("tomd.lib.golden_qa.subprocess.run", side_effect=FileNotFoundError):
        drafts = issue_for_stem("p4228r0", tmp_path)
    assert drafts
    assert not any("Localized gaps" in d for d in drafts)


# --- Task 7: validate_facts_jsonl ---

def test_validate_facts_jsonl_valid():
    text = (
        '{"type": "present", "text": "the rule", "checked": "verified"}\n'
        '{"type": "order", "sequence": ["A", "B"], "checked": "draft"}\n'
    )
    errors = validate_facts_jsonl(text)
    assert errors == []


def test_validate_facts_jsonl_bad_type():
    text = '{"type": "unknown", "text": "x", "checked": "verified"}\n'
    errors = validate_facts_jsonl(text)
    assert any("unknown type" in e for e in errors)


def test_validate_facts_jsonl_missing_text():
    text = '{"type": "present", "checked": "verified"}\n'
    errors = validate_facts_jsonl(text)
    assert any("requires 'text'" in e for e in errors)


def test_validate_facts_jsonl_bad_checked():
    text = '{"type": "present", "text": "x", "checked": "maybe"}\n'
    errors = validate_facts_jsonl(text)
    assert any("checked must be" in e for e in errors)


def test_validate_facts_jsonl_comments_ignored():
    text = "# this is a comment\n\n"
    assert validate_facts_jsonl(text) == []


def test_validate_facts_jsonl_bad_json():
    errors = validate_facts_jsonl("{bad json}\n")
    assert any("invalid JSON" in e for e in errors)


# --- Task 8: validate_anchors_json ---

def test_validate_anchors_json_valid():
    data = {
        "pid": "p0001r0",
        "surface": "normalized",
        "must_contain": ["section 3"],
        "must_not_contain": [],
        "ordered": ["Abstract", "References"],
        "patterns": [{"id": "docnum", "regex": "P0001R0"}]
    }
    errors = validate_anchors_json(data)
    assert errors == []


def test_validate_anchors_json_bad_surface():
    data = {"surface": "invalid"}
    errors = validate_anchors_json(data)
    assert any("surface" in e for e in errors)


def test_validate_anchors_json_bad_must_contain():
    data = {"must_contain": "not-a-list"}
    errors = validate_anchors_json(data)
    assert any("must_contain" in e for e in errors)


def test_validate_anchors_json_bad_pattern():
    data = {"patterns": [{"id": "x"}]}  # missing regex
    errors = validate_anchors_json(data)
    assert any("regex" in e for e in errors)
