#
# Copyright (c) 2026 Leo Chen (leo.chen0412@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

import pytest

from pipeline.tokens import tokens_to_chars


def make_large_issue_list_paper(*, issue_count: int, lines_per_issue: int) -> str:
    """Synthetic P4160R0 shape: one H2, many H4 issues, no H3."""
    issues = []
    for i in range(1, issue_count + 1):
        body = "\n".join(
            f"Wording detail line {j} for issue {i}." for j in range(1, lines_per_issue + 1)
        )
        issues.append(f"#### Issue {i}\n{body}")
    return (
        "---\n"
        "title: Ready Issues\n"
        "---\n\n"
        "## Ready issues in C++26\n\n"
        + "\n\n".join(issues)
    )


@pytest.fixture(scope="session")
def survey_max_chars() -> int:
    return tokens_to_chars(1000)


@pytest.fixture(scope="session")
def large_issue_list_paper() -> str:
    return make_large_issue_list_paper(issue_count=20, lines_per_issue=25)
