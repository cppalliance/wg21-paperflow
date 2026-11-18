"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from parity.corpus import PDF_CONVERTER_CASES, cached_parse_pdf
from parity.rawblock_allowlist import PDF_RAWBLOCK_ALLOWLIST
from tomd.domain.elements import RawBlock, UncertainElement


def test_pdf_rawblock_origin_ratchet():
    observed_origins: set[str] = set()
    uncertain_count = 0

    for path, extract_vector in PDF_CONVERTER_CASES:
        doc = cached_parse_pdf(path, extract_vector)
        for elem in doc.elements:
            if isinstance(elem, RawBlock):
                observed_origins.add(elem.origin)
            elif isinstance(elem, UncertainElement):
                uncertain_count += 1

    assert "pdf:uncertain" not in observed_origins
    assert uncertain_count > 0

    unexpected = sorted(observed_origins - PDF_RAWBLOCK_ALLOWLIST)
    retired = sorted(PDF_RAWBLOCK_ALLOWLIST - observed_origins)
    assert not unexpected and not retired, (
        f"PDF RawBlock origin ratchet mismatch.\n"
        f"Unexpected new origins (forbidden): {unexpected}\n"
        f"Retired origins (remove from PDF_RAWBLOCK_ALLOWLIST in this PR): {retired}"
    )
