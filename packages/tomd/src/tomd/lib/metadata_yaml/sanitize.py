"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""


import re

from tomd.domain.metadata import normalize_title

_TITLE_LABEL_RE = re.compile(
    r"(?:Paper\s*Number|Document(?:\s*Number)?|Title|Authors?|"
    r"Acknowledgements?|Reply[- ]?to|Audience|Date)\s*:",
    re.IGNORECASE,
)

_DOUBLE_ANGLE_RE = re.compile(r"<\s*<([^>]+)>")

_NON_AUTHOR_RE = re.compile(
    r"^(?:Target|Proposed|Wording|Structures?|Version|Contents?|"
    r"Read-Copy|Abstract|Introduction|Overview|Revision)\b",
    re.IGNORECASE,
)


def sanitize_metadata(metadata: dict) -> dict:
    """Clean up extracted metadata values before formatting.

    Fixes: embedded newlines in title, metadata labels in title text,
    double angle brackets in reply-to entries, non-author reply-to values.
    """
    md = dict(metadata)

    if "title" in md and not isinstance(md["title"], str):
        md["title"] = str(md["title"])

    if "title" in md:
        title = normalize_title(md["title"])
        title_label_m = re.search(r"\bTitle\s*:\s*", title, re.IGNORECASE)
        if title_label_m:
            after_title = title[title_label_m.end():].strip()
            next_label = _TITLE_LABEL_RE.search(after_title)
            if next_label:
                title = after_title[:next_label.start()].rstrip(" ,;")
            elif after_title:
                title = after_title
        else:
            m = _TITLE_LABEL_RE.search(title)
            if m and m.start() > 0:
                title = title[:m.start()].rstrip(" ,;")
            elif m and m.start() == 0:
                after_label = title[m.end():].strip()
                next_label = _TITLE_LABEL_RE.search(after_label)
                if next_label:
                    title = after_label[:next_label.start()].rstrip(" ,;")
                elif after_label:
                    title = after_label
        md["title"] = title.strip()

    if isinstance(md.get("reply-to"), str):
        md["reply-to"] = [md["reply-to"]]

    if "reply-to" in md and isinstance(md["reply-to"], list):
        cleaned = []
        for entry in md["reply-to"]:
            entry = _DOUBLE_ANGLE_RE.sub(r"<\1>", entry)
            if _NON_AUTHOR_RE.match(entry.strip()):
                continue
            cleaned.append(entry)
        if cleaned:
            md["reply-to"] = cleaned
        else:
            del md["reply-to"]

    return md
