#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""whisker survey: repeatable monthly competitor monitor.

Public API re-exports for the survey subpackage.
"""

from whisker.survey.cli import survey_main
from whisker.survey.history import (
    DUE_INTERVAL_DAYS,
    append_run,
    is_due,
    last_successful_run,
    load_history,
)
from whisker.survey.registry import (
    CompetitorSpec,
    PatchSpec,
    get_competitor,
    list_competitors,
    load_lockfile,
)
from whisker.survey.report import (
    AUSSAGEGRENZEN_TEXT,
    aussagegrenzen_text,
    build_report_json,
    render_report_md,
    write_report,
)
from whisker.survey.runner import (
    CorpusContract,
    CorpusPaper,
    canonicalize_for_lane2,
    load_corpus,
)
from whisker.survey.runtime import (
    build_env_dict,
    cache_root,
    is_installed,
    verify_integrity,
)

__all__ = [
    "AUSSAGEGRENZEN_TEXT",
    "aussagegrenzen_text",
    "CompetitorSpec",
    "CorpusContract",
    "CorpusPaper",
    "DUE_INTERVAL_DAYS",
    "PatchSpec",
    "append_run",
    "build_env_dict",
    "build_report_json",
    "cache_root",
    "canonicalize_for_lane2",
    "get_competitor",
    "is_due",
    "is_installed",
    "last_successful_run",
    "list_competitors",
    "load_corpus",
    "load_history",
    "load_lockfile",
    "render_report_md",
    "survey_main",
    "verify_integrity",
    "write_report",
]
