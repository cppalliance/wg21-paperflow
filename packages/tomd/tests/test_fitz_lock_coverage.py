# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Enforcement: every file in lib/pdf/ that opens a fitz Document must acquire _FITZ_LOCK."""

from pathlib import Path

# Scans lib/pdf/ only. If fitz usage is ever added outside this directory,
# extend PDF_LIB or add a second scan path here.
_PDF_LIB = Path(__file__).resolve().parent.parent / "src" / "tomd" / "lib" / "pdf"

# Covers fitz.open(), fitz.Document(), and the _fitz alias used in docling_backend.py.
# A file using any other import alias (e.g. `import fitz as pdf`) will not be detected.
# If a new alias is introduced, add its .open() and .Document() forms here.
_FITZ_OPEN_PATTERNS = ("fitz.open(", "fitz.Document(", "_fitz.open(", "_fitz.Document(")


def test_all_fitz_document_openers_acquire_lock():
    for path in sorted(_PDF_LIB.rglob("*.py")):
        if path.name.startswith("._"):
            continue
        source = path.read_text(encoding="utf-8")
        if not any(p in source for p in _FITZ_OPEN_PATTERNS):
            continue
        # Note: this checks that _FITZ_LOCK is referenced in the source, not that it
        # is correctly used as a context manager. Code review remains the backstop
        # for ensuring the lock wraps the full open/close session.
        assert "_FITZ_LOCK" in source, (
            f"{path.name} opens a fitz Document but does not acquire _FITZ_LOCK"
        )
