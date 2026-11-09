"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from tomd.domain.document import PaperDocument


@runtime_checkable
class DocumentParser(Protocol):
    """Uniform front-end interface for document source parsers."""

    def parse(self, path: Path) -> PaperDocument:
        """Parse a document source file into a PaperDocument AST."""
        ...
