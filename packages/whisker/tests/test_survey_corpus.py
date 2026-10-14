#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for whisker.survey.runner: corpus contract validation."""

import json

import pytest
from whisker.survey.runner import CorpusContract, load_corpus


@pytest.fixture
def corpus_dir(tmp_path):
    """Create a minimal valid corpus structure."""
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    golden = tmp_path / "golden"
    golden.mkdir()

    papers = []
    for pid in ("P1000R0", "P2000R0"):
        # Create PDF
        pdf = pdfs / f"{pid}.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        # Create ideal
        ideal = golden / f"{pid}.ideal.md"
        ideal.write_text(f"# {pid}\n\nSample ideal.\n", encoding="utf-8")
        # Create facts
        facts = golden / f"{pid}.facts.jsonl"
        fact_record = json.dumps({
            "id": f"prose-{pid}",
            "type": "present",
            "checked": "verified",
            "text": "sample text",
        })
        facts.write_text(fact_record + "\n", encoding="utf-8")
        papers.append({
            "pid": pid,
            "pdf": f"pdfs/{pid}.pdf",
            "page_count": 3,
            "structure_class": "tables",
        })

    corpus_json = {
        "corpus_version": 1,
        "frozen": "2026-08-01",
        "papers": papers,
    }
    (tmp_path / "corpus.json").write_text(
        json.dumps(corpus_json, indent=2), encoding="utf-8"
    )
    return tmp_path


class TestCorpusLoading:
    """Corpus contract validation tests."""

    def test_load_valid_corpus(self, corpus_dir):
        corpus = load_corpus(corpus_dir)
        assert isinstance(corpus, CorpusContract)
        assert corpus.corpus_version == 1
        assert len(corpus.papers) == 2

    def test_corpus_version_propagation(self, corpus_dir):
        corpus = load_corpus(corpus_dir)
        assert corpus.corpus_version == 1

        # Update version
        data = json.loads((corpus_dir / "corpus.json").read_text(encoding="utf-8"))
        data["corpus_version"] = 2
        (corpus_dir / "corpus.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        corpus2 = load_corpus(corpus_dir)
        assert corpus2.corpus_version == 2

    def test_missing_corpus_json(self, tmp_path):
        with pytest.raises(RuntimeError, match="corpus.json not found"):
            load_corpus(tmp_path)

    def test_missing_corpus_version(self, corpus_dir):
        data = json.loads((corpus_dir / "corpus.json").read_text(encoding="utf-8"))
        del data["corpus_version"]
        (corpus_dir / "corpus.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        with pytest.raises(RuntimeError, match="missing corpus_version"):
            load_corpus(corpus_dir)

    def test_missing_ideal_aborts(self, corpus_dir):
        # Remove one ideal
        ideal = corpus_dir / "golden" / "P1000R0.ideal.md"
        ideal.unlink()
        with pytest.raises(RuntimeError, match="Ideal not found.*P1000R0"):
            load_corpus(corpus_dir)

    def test_missing_facts_aborts(self, corpus_dir):
        # Remove one facts file
        facts = corpus_dir / "golden" / "P2000R0.facts.jsonl"
        facts.unlink()
        with pytest.raises(RuntimeError, match="Facts not found.*P2000R0"):
            load_corpus(corpus_dir)

    def test_missing_pdf_aborts(self, corpus_dir):
        pdf = corpus_dir / "pdfs" / "P1000R0.pdf"
        pdf.unlink()
        with pytest.raises(RuntimeError, match="PDF not found.*P1000R0"):
            load_corpus(corpus_dir)

    def test_empty_papers_aborts(self, corpus_dir):
        data = json.loads((corpus_dir / "corpus.json").read_text(encoding="utf-8"))
        data["papers"] = []
        (corpus_dir / "corpus.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        with pytest.raises(RuntimeError, match="no papers"):
            load_corpus(corpus_dir)

    def test_resolved_paths_are_carried_on_the_paper(self, corpus_dir):
        """Ideal and facts paths must survive loading, not just be validated.

        load_corpus resolves both and checks they exist, then used to drop them.
        Callers had to rebuild the paths themselves, and the survey CLI rebuilt
        them from the retired v1 layout, so Lanes 2 and 3 scored against files
        that were not there.
        """
        corpus = load_corpus(corpus_dir)
        for paper in corpus.papers:
            assert paper.ideal_path.is_file(), paper.pid
            assert paper.facts_path.is_file(), paper.pid
            assert paper.pdf_path.is_file(), paper.pid


class TestRealBenchmarkCorpus:
    """The shipped corpus must load through the path the CLI actually uses."""

    def test_cli_bench_root_reaches_the_corpus(self):
        """`survey run` passes _default_bench_root()/corpus to load_corpus.

        This pairing was broken and unnoticed: the CLI passed the bench root
        itself, so every run died on "corpus.json not found" before converting
        anything. The benchmark was driven by the tools/ scripts, which never
        exercised this path.
        """
        from whisker.survey.cli import _default_bench_root

        bench = _default_bench_root()
        if not (bench / "corpus" / "corpus.json").is_file():
            pytest.skip("benchmark corpus not present in this checkout")

        corpus = load_corpus(bench / "corpus")
        assert corpus.papers
        for paper in corpus.papers:
            assert paper.ideal_path.is_file(), paper.pid
            assert paper.facts_path.is_file(), paper.pid
