#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ASSAY_ROOT = Path(__file__).resolve().parents[1]
_JSONL = _ASSAY_ROOT / "data" / "golden" / "paper_categories.jsonl"
_VALIDATE = _ASSAY_ROOT / "study" / "golden" / "validate_categories.py"


def test_golden_categories_validate_exits_zero():
    result = subprocess.run(
        [sys.executable, str(_VALIDATE), str(_JSONL)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"validate_categories failed:\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
