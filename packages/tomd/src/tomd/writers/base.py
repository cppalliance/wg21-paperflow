"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from typing import Any, Protocol, runtime_checkable

from tomd.domain.document import PaperDocument


@runtime_checkable
class DocumentWriter(Protocol):
    """Uniform backend interface for document emitters."""

    def write(
        self,
        document: PaperDocument,
        meta: dict[str, Any] | None = None,
    ) -> str:
        """Format a PaperDocument into output text representation."""
        ...
