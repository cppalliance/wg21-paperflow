#
# Copyright (c) 2026 Henry Wang (henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

from assay.heading_classifiers import (
    HeadingKind,
    is_acknowledgment_heading,
    is_appendix_heading_line,
    is_reference_heading,
    is_revision_heading,
)


def test_is_revision_heading_yes():
    assert is_revision_heading("## Revision History") is HeadingKind.YES


def test_is_revision_heading_no():
    assert is_revision_heading("## Motivation") is HeadingKind.NO


def test_is_revision_heading_unknown():
    assert is_revision_heading("plain text") is HeadingKind.UNKNOWN


def test_is_reference_heading_yes():
    assert is_reference_heading("## References") is HeadingKind.YES


def test_is_acknowledgment_heading_yes():
    assert is_acknowledgment_heading("## Acknowledgements") is HeadingKind.YES


def test_is_appendix_heading_line_reference():
    assert is_appendix_heading_line("## References")


def test_is_appendix_heading_line_appendix_keyword():
    assert is_appendix_heading_line("## Appendix A")


def test_is_appendix_heading_line_motivation_false():
    assert not is_appendix_heading_line("## Motivation")


def test_is_revision_heading_override():
    assert (
        is_revision_heading("## Revision log", {"revision log"})
        is HeadingKind.YES
    )
