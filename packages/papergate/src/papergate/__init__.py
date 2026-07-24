#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""PaperGate on PromptForge.

PaperGate reads a WG21 paper, strips it to the rationale it contains, and
reports what that rationale shows - and fails to show - as evidence for
standardization. It is the acceptance pipeline for the PromptForge runtime: a
Digest subagent strips and classifies, an Evaluate subagent applies the
criteria and writes the report, and Main orchestrates without reading the paper.
"""

from __future__ import annotations

__version__ = "0.4.1"

__all__ = ["__version__"]
