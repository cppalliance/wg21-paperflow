"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

FRONT_MATTER_ORDER = ("title", "document", "date", "intent", "audience", "reply-to")


def is_blank_value(value: object) -> bool:
    """True for ``None``, empty or whitespace-only text, and lists with no non-blank item.

    A blank front-matter value counts as missing: it is never emitted, and the
    mailing fallback fills it.
    """
    if value is None:
        return True
    if isinstance(value, (list, tuple)):
        return all(is_blank_value(item) for item in value)
    return not str(value).strip()
