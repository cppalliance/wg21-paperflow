"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.parsers.pdf.adapter import (
    ADAPTERS,
    convert_pdf_dark,
    parse_pdf,
    sections_to_document,
)

__all__ = [
    "ADAPTERS",
    "convert_pdf_dark",
    "parse_pdf",
    "sections_to_document",
]
