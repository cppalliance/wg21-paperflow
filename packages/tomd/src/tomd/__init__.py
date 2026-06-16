"""tomd: PDF and HTML to Markdown converter for WG21 papers."""

from tomd.api import ConvertedPaper, convert_paper, convert_paper_full
from tomd.errors import (
    CheckContentArgError,
    TomdError,
    UnsupportedSourceFormatError,
)

__all__ = [
    "CheckContentArgError",
    "TomdError",
    "UnsupportedSourceFormatError",
    "convert_paper",
    "convert_paper_full",
    "ConvertedPaper",
]
