#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Shared audience-phrase matching for the hand and learned aggregators."""

from __future__ import annotations

import re


def audience_blob(audience: list[str] | None) -> str:
    return " ".join(audience or []).upper()


def audience_has_phrase(blob: str, phrase: str) -> bool:
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b"
    return re.search(pattern, blob) is not None
