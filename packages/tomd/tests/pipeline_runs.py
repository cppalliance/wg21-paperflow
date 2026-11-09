"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from functools import lru_cache
from pathlib import Path

from tomd.lib.pdf.pipeline import PipelineResult, run_pipeline


@lru_cache(maxsize=None)
def shared_run_pipeline(path: Path) -> PipelineResult:
    """Run ``run_pipeline(path)`` with default options once per test session.

    The golden and parity suites convert the same fixture PDFs, and the large
    ones dominate the suite's runtime (and the Windows CI time limit). Callers
    share one result and must treat it as read-only.
    """
    return run_pipeline(path)
