"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExtractedImage:
    """Canonical representation of an extracted figure or illustration."""

    stored_filename: str
    bytes: "bytes | None" = None
    caption: str = ""
    alt: str = ""
    source: str = "raster"


@dataclass(frozen=True)
class ImageRef:
    """Format-neutral reference to an image within a document."""

    stored_filename: str
    caption: str = ""
    alt: str = ""
    source_path: Path | None = None
