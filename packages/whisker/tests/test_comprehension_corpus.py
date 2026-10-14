#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Lane 3 comprehension gate over the committed micro-corpus.

This is the CI-hermetic counterpart to the ``whisker facts`` CLI: the CLI reads
the candidate from the paperstore backend (``data/``, gitignored, absent in CI),
so it cannot gate in CI. Here the substrate is the committed
``corpus/<pid>.expected.md`` snapshot, so the comprehension assertions run with
no backend, no ``data/``, and no LLM.

For each paper that ships BOTH a ``<pid>.facts.jsonl`` and a
``<pid>.expected.md``, every ``checked: verified`` fact must hold against the
snapshot. A scrambled snapshot must fail (the canary), so a vacuous green is
ruled out from both sides.
"""

from pathlib import Path

import pytest
from whisker.facts import check_facts, parse_facts_jsonl

_CORPUS = Path(__file__).resolve().parent.parent / "corpus"
_FACTS_SUFFIX = ".facts.jsonl"
_EXPECTED_SUFFIX = ".expected.md"


def _corpus_pairs() -> list[tuple[str, Path, Path]]:
    """(pid, facts_path, expected_path) for papers with both artifacts.

    A facts file without a committed snapshot has no hermetic substrate, so it
    is skipped here (it is still exercised against ``data/`` by the CLI).

    golden-hook: construct-isolated golden pairs (``<case>.in.html`` /
    ``<case>.out.md``, one construct per case, following html-to-markdown-go's
    ``goldenfiles.go``) plug in here as a second substrate source next to the
    whole-paper ``expected.md`` snapshots. Whole-paper snapshots catch drift;
    construct pairs localize WHICH construct broke without human triage.
    """
    pairs: list[tuple[str, Path, Path]] = []
    for facts_path in sorted(_CORPUS.glob(f"*{_FACTS_SUFFIX}")):
        pid = facts_path.name[: -len(_FACTS_SUFFIX)].upper()
        expected_path = _CORPUS / f"{pid}{_EXPECTED_SUFFIX}"
        if expected_path.is_file():
            pairs.append((pid, facts_path, expected_path))
    return pairs


_PAIRS = _corpus_pairs()
_IDS = [pid for pid, _, _ in _PAIRS]


def test_corpus_has_at_least_one_comprehension_paper():
    # Guard against a vacuous suite: if every paper lost its snapshot the
    # parametrized test below would silently collect nothing and pass.
    assert _PAIRS, (
        f"no <pid>{_FACTS_SUFFIX} + <pid>{_EXPECTED_SUFFIX} pairs found in {_CORPUS}"
    )


@pytest.mark.parametrize(("pid", "facts_path", "expected_path"), _PAIRS, ids=_IDS)
def test_verified_facts_hold_against_snapshot(pid, facts_path, expected_path):
    md = expected_path.read_text(encoding="utf-8")
    facts = parse_facts_jsonl(facts_path.read_text(encoding="utf-8-sig"), pid)

    report = check_facts(md, facts, pid)

    # A paper with a committed facts file must enforce at least one fact, else
    # the snapshot proves nothing about comprehension.
    verified = [c for c in report.checks if c.verified]
    assert verified, f"{pid}: facts file has no checked:verified fact"

    if report.failed:
        lines = "\n".join(f"  {c.id} ({c.type}): {c.detail}" for c in report.failures())
        pytest.fail(f"{pid}: verified comprehension fact(s) failed:\n{lines}")


def test_canary_scrambled_table_cell_fails():
    # Proves the gate has teeth: corrupting one Table A cell of the P4182R0
    # snapshot must flip the corresponding verified table fact to a failure.
    pid = "P4182R0"
    expected_path = _CORPUS / f"{pid}{_EXPECTED_SUFFIX}"
    facts_path = _CORPUS / f"{pid}{_FACTS_SUFFIX}"
    if not (expected_path.is_file() and facts_path.is_file()):
        pytest.skip(f"{pid} corpus artifacts not present")

    md = expected_path.read_text(encoding="utf-8")
    needle = "(CUDA, SYCL) | No |"
    assert needle in md, "canary anchor drifted; update the scramble target"
    scrambled = md.replace(needle, "(CUDA, SYCL) | Yes |", 1)

    facts = parse_facts_jsonl(facts_path.read_text(encoding="utf-8-sig"), pid)
    report = check_facts(scrambled, facts, pid)

    assert report.failed, "scrambled snapshot must fail the comprehension gate"
    assert any(c.id == "tableA-gpu-coro-no" for c in report.failures())


def test_canary_scrambled_code_fails():
    # Proves the code gate has teeth: mangling the asm-alias snippet in the
    # P4234R0 snapshot must flip the corresponding verified code fact.
    pid = "P4234R0"
    expected_path = _CORPUS / f"{pid}{_EXPECTED_SUFFIX}"
    facts_path = _CORPUS / f"{pid.lower()}{_FACTS_SUFFIX}"
    if not (expected_path.is_file() and facts_path.is_file()):
        pytest.skip(f"{pid} corpus artifacts not present")

    md = expected_path.read_text(encoding="utf-8")
    needle = 'asm("Image$$ER_ZI$$Base")'
    assert needle in md, "canary anchor drifted; update the scramble target"
    scrambled = md.replace(needle, 'asm("Image__ER_ZI__Base")', 1)

    facts = parse_facts_jsonl(facts_path.read_text(encoding="utf-8-sig"), pid)
    report = check_facts(scrambled, facts, pid)

    assert report.failed, "scrambled code snippet must fail the comprehension gate"
    assert any(c.id == "code-asm-alias" for c in report.failures())


def test_canary_scrambled_formula_fails():
    # Proves the math gate has teeth: flipping the relation in one verified
    # P4185R0 formula (>= to <=) must flip its math fact to a failure.
    pid = "P4185R0"
    expected_path = _CORPUS / f"{pid}{_EXPECTED_SUFFIX}"
    facts_path = _CORPUS / f"{pid}{_FACTS_SUFFIX}"
    if not (expected_path.is_file() and facts_path.is_file()):
        pytest.skip(f"{pid} corpus artifacts not present")

    md = expected_path.read_text(encoding="utf-8")
    needle = r"\(x^{2k} \geq 0\)"
    assert needle in md, "canary anchor drifted; update the scramble target"
    scrambled = md.replace(needle, r"\(x^{2k} \leq 0\)", 1)

    facts = parse_facts_jsonl(facts_path.read_text(encoding="utf-8-sig"), pid)
    report = check_facts(scrambled, facts, pid)

    assert report.failed, "scrambled formula must fail the comprehension gate"
    assert any(c.id == "math-even-power-nonneg" for c in report.failures())


def test_canary_arrow_operator_corruption_fails():
    """Proves the raw-surface gate has teeth against operator corruption.

    Audit finding CR1: the deterministic scoring lane cannot distinguish
    ``p->next`` from ``p.next`` (both alnum-fold to the same normalized
    text, see ``research/research/Audit/Auditv4/signal-separation-measurement.md``).
    Lane 3 facts see the raw surface instead, so rewriting the arrow
    dereference in the P0876R23 ``code-fiber-example`` snippet must flip
    that verified code fact to a failure. This is the load-bearing addition:
    the class the scoring lane is provably blind to.
    """
    pid = "P0876R23"
    expected_path = _CORPUS / f"{pid}{_EXPECTED_SUFFIX}"
    facts_path = _CORPUS / f"{pid.lower()}{_FACTS_SUFFIX}"
    if not (expected_path.is_file() and facts_path.is_file()):
        pytest.skip(f"{pid} corpus artifacts not present")

    md = expected_path.read_text(encoding="utf-8")
    needle = "pf1->resume();"
    assert needle in md, "canary anchor drifted; update the scramble target"
    scrambled = md.replace(needle, "pf1.resume();", 1)

    facts = parse_facts_jsonl(facts_path.read_text(encoding="utf-8-sig"), pid)
    report = check_facts(scrambled, facts, pid)

    assert report.failed, "arrow-to-dot operator corruption must fail the comprehension gate"
    assert any(c.id == "code-fiber-example" for c in report.failures())


def test_canary_semicolon_punctuation_corruption_fails():
    """Proves the raw-surface gate has teeth against punctuation corruption.

    Audit finding CR1 also names bare punctuation swaps as invisible to the
    alnum-folded scoring lane. Corrupting the trailing semicolon of the
    P4234R0 raw-surface declaration (``dollar-dollar-survives``) must flip
    that verified present fact, even though every alphanumeric token in the
    line is unchanged.
    """
    pid = "P4234R0"
    expected_path = _CORPUS / f"{pid}{_EXPECTED_SUFFIX}"
    facts_path = _CORPUS / f"{pid.lower()}{_FACTS_SUFFIX}"
    if not (expected_path.is_file() and facts_path.is_file()):
        pytest.skip(f"{pid} corpus artifacts not present")

    md = expected_path.read_text(encoding="utf-8")
    needle = "extern int Image$$ER_ZI$$Base;"
    assert needle in md, "canary anchor drifted; update the scramble target"
    scrambled = md.replace(needle, "extern int Image$$ER_ZI$$Base,", 1)

    facts = parse_facts_jsonl(facts_path.read_text(encoding="utf-8-sig"), pid)
    report = check_facts(scrambled, facts, pid)

    assert report.failed, "semicolon-to-comma corruption must fail the comprehension gate"
    assert any(c.id == "dollar-dollar-survives" for c in report.failures())


def test_canary_permuted_headings_fails():
    """Proves the order gate has teeth against reading-order permutation.

    Swapping two adjacent subsection headings in the N5040 minutes (bodies
    left untouched) reverses their relative reading position without
    dropping a single word, so ``unigram_coverage``-style content checks
    would stay green. The corresponding verified ``order-headings`` fact
    must catch the swap.
    """
    pid = "N5040"
    expected_path = _CORPUS / f"{pid}{_EXPECTED_SUFFIX}"
    facts_path = _CORPUS / f"{pid.lower()}{_FACTS_SUFFIX}"
    if not (expected_path.is_file() and facts_path.is_file()):
        pytest.skip(f"{pid} corpus artifacts not present")

    md = expected_path.read_text(encoding="utf-8")
    heading_a = "### 1.1. Opening comments, welcome from host"
    heading_b = "### 1.2. Meeting guidelines"
    assert heading_a in md and heading_b in md, "canary anchor drifted; update the scramble target"
    swap_placeholder = "\x00CANARY_HEADING_SWAP\x00"
    permuted = md.replace(heading_a, swap_placeholder, 1)
    permuted = permuted.replace(heading_b, heading_a, 1)
    permuted = permuted.replace(swap_placeholder, heading_b, 1)

    facts = parse_facts_jsonl(facts_path.read_text(encoding="utf-8-sig"), pid)
    report = check_facts(permuted, facts, pid)

    assert report.failed, "permuted headings must fail the comprehension gate"
    assert any(c.id == "order-headings" for c in report.failures())


# -- Canary coverage matrix (meta-test) --------------------------------------

# Every corruption class the hermetic battery is required to catch, mapped to
# the name of the test function that proves it. Deleting or renaming that
# function without updating this table fails ``test_canary_coverage_matrix_
# complete`` below, so a future refactor cannot silently drop teeth.
_REQUIRED_CANARY_CLASSES: dict[str, str] = {
    "table_cell_value_swap": "test_canary_scrambled_table_cell_fails",
    "code_identifier_mangle": "test_canary_scrambled_code_fails",
    "math_relation_flip": "test_canary_scrambled_formula_fails",
    "raw_surface_arrow_operator": "test_canary_arrow_operator_corruption_fails",
    "raw_surface_punctuation": "test_canary_semicolon_punctuation_corruption_fails",
    "reading_order_permutation": "test_canary_permuted_headings_fails",
}

# Corruption classes named by the audit that this battery deliberately does
# NOT cover, with the reason. Listed explicitly so the gap is visible rather
# than silently absent from ``_REQUIRED_CANARY_CLASSES``.
_EXCLUDED_CANARY_CLASSES: dict[str, str] = {
    "reference_qualifier_corruption(T&&_vs_T&)": (
        "no existing checked:verified fact's asserted text contains a "
        "reference-qualifier token (&& vs &); authoring one would require "
        "a new verified fact, and blessing a fact to verified is a manual "
        "human step the tooling must never perform itself "
        "(see whisker/src/whisker/CLAUDE.md)"
    ),
}

# Corpus papers that must carry at least one canary. Closes the wave-2
# zero-coverage gap: before this change N5040 and P0876R23 had committed
# snapshots and verified facts but no canary exercising either.
_REQUIRED_CANARY_PAPERS: dict[str, str] = {
    "P4182R0": "test_canary_scrambled_table_cell_fails",
    "P4185R0": "test_canary_scrambled_formula_fails",
    "P4234R0": "test_canary_scrambled_code_fails",
    "N5040": "test_canary_permuted_headings_fails",
    "P0876R23": "test_canary_arrow_operator_corruption_fails",
}


def test_canary_coverage_matrix_complete():
    """Meta-test: every required corruption class maps to a live canary.

    Driven entirely from ``_REQUIRED_CANARY_CLASSES`` /
    ``_EXCLUDED_CANARY_CLASSES``: a class must appear in exactly one of the
    two tables, and every covering entry must resolve to a callable
    ``test_canary_*`` function that still exists in this module.
    """
    registry = globals()
    overlap = set(_REQUIRED_CANARY_CLASSES) & set(_EXCLUDED_CANARY_CLASSES)
    assert not overlap, f"class(es) both covered and excluded: {sorted(overlap)}"

    for corruption_class, test_name in _REQUIRED_CANARY_CLASSES.items():
        fn = registry.get(test_name)
        assert callable(fn), (
            f"{corruption_class}: canary test {test_name!r} missing or not callable"
        )
        assert test_name.startswith("test_canary_"), (
            f"{corruption_class}: {test_name!r} is not a canary test"
        )

    for corruption_class, reason in _EXCLUDED_CANARY_CLASSES.items():
        assert reason.strip(), f"{corruption_class}: exclusion reason must not be empty"


def test_canary_paper_coverage_complete():
    """Meta-test: every listed corpus paper carries at least one live canary.

    Driven from ``_REQUIRED_CANARY_PAPERS``: renaming/deleting the mapped
    canary, or losing the paper's discovered facts/expected pair, fails
    here instead of silently regressing to zero coverage.
    """
    registry = globals()
    for pid, test_name in _REQUIRED_CANARY_PAPERS.items():
        assert pid in _IDS, f"{pid}: not a discovered corpus pair (facts/expected.md drifted?)"
        fn = registry.get(test_name)
        assert callable(fn), f"{pid}: canary test {test_name!r} missing or not callable"
