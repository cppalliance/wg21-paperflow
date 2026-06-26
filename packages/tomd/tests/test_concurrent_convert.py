# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Regression test: concurrent PDF conversion must not corrupt per-paper output.

Fixture PDFs live in fixtures/concurrent/. See the README.md there for details.
If the fixtures are not committed, the test is skipped automatically.
"""

import threading
from pathlib import Path

import pytest

from tomd.lib.pdf import run_pipeline

_CONCURRENT = Path(__file__).resolve().parent / "fixtures" / "concurrent"
_P4003R1 = _CONCURRENT / "p4003r1.pdf"
_P3127R1 = _CONCURRENT / "p3127r1.pdf"


def test_concurrent_convert_no_spurious_vector_images():
    """P4003R1 converted concurrently with P3127R1 must not produce spurious page-57 vectors.

    Without _FITZ_LOCK, the cross-page table filter in pipeline.py loses its
    prior-page TABLE bbox due to MuPDF shared-state corruption, and fig57-1.png /
    fig57-2.png survive in the output.
    """
    if not _P4003R1.is_file():
        pytest.skip(f"fixture not committed yet: {_P4003R1.name}")
    if not _P3127R1.is_file():
        pytest.skip(f"fixture not committed yet: {_P3127R1.name}")

    results = [None, None]
    errors = [None, None]

    def run(idx, path):
        try:
            results[idx] = run_pipeline(path, extract_vector=True)
        except Exception as exc:  # thread exceptions are swallowed by join()
            errors[idx] = exc

    t1 = threading.Thread(target=run, args=(0, _P4003R1))
    t2 = threading.Thread(target=run, args=(1, _P3127R1))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    for err in errors:
        if err:
            raise err

    page57_vectors = [
        im for im in results[0].images if im.page == 57 and im.source == "vector"
    ]
    assert page57_vectors == [], (
        f"Expected no vector images on page 57 of P4003R1, got {len(page57_vectors)}: "
        f"{[im.stored_filename for im in page57_vectors]}"
    )
