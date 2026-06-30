#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Shared markdown heading patterns for pipeline consumers."""

from __future__ import annotations

import re

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
BOLD_SUBSECTION_RE = re.compile(r"^\*\*\d+(?:\.\d+)+\*\*")
