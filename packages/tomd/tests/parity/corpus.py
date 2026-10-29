"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

from tomd.domain.document import PaperDocument
from tomd.lib.pdf import vector_images
from tomd.lib.pdf.pipeline import PipelineResult, run_pipeline
import tomd.parsers.pdf.adapter as pdf_adapter
from tomd.parsers.pdf import parse_pdf

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"
STEMS_DIR = GOLDEN_DIR / "stems"


def _resolve_golden_pdf(stem: str) -> Path:
    source_path = GOLDEN_DIR / "sources" / f"{stem}.pdf"
    if source_path.is_file():
        return source_path
    root_path = GOLDEN_DIR / f"{stem}.pdf"
    if root_path.is_file():
        return root_path
    raise FileNotFoundError(f"Missing PDF fixture for golden stem {stem!r}")


def discover_golden_pdfs() -> tuple[Path, ...]:
    """Return the 28 PDF paths corresponding to fixtures/golden/stems/*.txt."""
    stems = sorted(p.stem for p in STEMS_DIR.glob("*.txt"))
    return tuple(_resolve_golden_pdf(stem) for stem in stems)


def discover_synth_pdfs() -> tuple[Path, ...]:
    """Return the 4 synthetic vector/table PDF fixtures in tests/fixtures/."""
    return tuple(sorted(FIXTURES_DIR.glob("synth_*.pdf")))


GOLD_STANDARD_PDF = FIXTURES_DIR / "p2583r3-gold-standard.pdf"
GOLDEN_PDF_CORPUS: tuple[Path, ...] = discover_golden_pdfs()
SYNTH_PDF_CORPUS: tuple[Path, ...] = discover_synth_pdfs()
PDF_CORPUS: tuple[Path, ...] = (
    *GOLDEN_PDF_CORPUS,
    *SYNTH_PDF_CORPUS,
    GOLD_STANDARD_PDF,
)

PDF_CONVERTER_CASES: tuple[tuple[Path, bool], ...] = (
    *((path, False) for path in PDF_CORPUS),
    *((path, True) for path in SYNTH_PDF_CORPUS),
)


@lru_cache(maxsize=None)
def _run_pipeline_cached(
    path: Path,
    extract_vector: bool,
    whiteout_text: bool,
) -> PipelineResult:
    if extract_vector and path.name.startswith("synth_"):
        with (
            patch.object(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1),
            patch.object(vector_images, "_LOW_OVERLAP_ADMIT_MIN_ITEMS", 1),
        ):
            return run_pipeline(
                path,
                extract_vector=True,
                whiteout_text=whiteout_text,
            )
    return run_pipeline(
        path,
        extract_vector=extract_vector,
        whiteout_text=whiteout_text,
    )


def cached_run_pipeline(
    path: Path,
    extract_vector: bool = False,
    whiteout_text: bool = False,
) -> PipelineResult:
    """Run ``run_pipeline`` once per ``(path, extract_vector, whiteout_text)`` across the test session."""
    path = Path(path)
    return _run_pipeline_cached(path, extract_vector, whiteout_text)


@lru_cache(maxsize=None)
def cached_parse_pdf(path: Path, extract_vector: bool = False) -> PaperDocument:
    """Run ``parse_pdf`` once per ``(path, extract_vector)``, reusing cached pipeline output."""
    with patch.object(pdf_adapter, "run_pipeline", side_effect=cached_run_pipeline):
        return parse_pdf(path, extract_vector=extract_vector)
