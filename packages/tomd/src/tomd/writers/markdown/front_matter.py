"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.domain.metadata import PaperMetadata
from tomd.lib.metadata_yaml.format import format_front_matter


def write_front_matter(metadata: PaperMetadata) -> str:
    """Format metadata as YAML front matter via the canonical ``format_front_matter``."""
    return format_front_matter(metadata.to_dict())


__all__ = ["write_front_matter"]
