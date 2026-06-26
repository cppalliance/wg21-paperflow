#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

from pipeline.heading_classifiers import (
    HeadingKind,
    classify_routing_section,
    is_acknowledgment_heading,
    is_appendix_heading_line,
    is_reference_heading,
    is_revision_heading,
)
from pipeline.paper_routing.types import SectionType


def test_classify_routing_section_motivation():
    assert classify_routing_section("Motivation and Scope") == SectionType.MOTIVATION


def test_classify_routing_section_wording():
    assert classify_routing_section("Proposed Wording") == SectionType.WORDING


def test_classify_routing_section_design_default():
    assert classify_routing_section("Technical Details") == SectionType.DESIGN


def test_classify_routing_section_appendix():
    assert classify_routing_section("References") == SectionType.APPENDIX


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
        is_revision_heading("## Old revision history notes", {"old revision history"})
        is HeadingKind.YES
    )
