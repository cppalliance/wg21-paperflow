"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

PDF_RAWBLOCK_ALLOWLIST: frozenset[str] = frozenset({
    "pdf:code",
    "pdf:heading",
    "pdf:image",
    "pdf:list",
    "pdf:paragraph",
    "pdf:table:html_table",
    "pdf:table:pipe_table",
    "pdf:title",
    "pdf:wording",
    "pdf:wording-add",
    "pdf:wording-remove",
})
