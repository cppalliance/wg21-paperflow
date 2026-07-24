#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""PaperGate domain tools.

Five thin, flat-signature functions. ``fetch_paper`` acquires the paper text;
the rest write to the current section's store (via the runtime's ambient
context) so state accrues one validated call at a time:

- ``fetch_paper`` - acquire by path, URL, or WG21 document number.
- ``set_metadata`` / ``acquisition_failed`` - file paper identity, or a clean
  acquisition-failure status so the pipeline can stop without fabricating.
- ``file_section`` / ``file_missing`` - record an addressed criterion or an
  absent one.
- ``write_report`` - render the filed sections plus the single closing
  ``## Missing From The Paper`` paragraph into a virtual file.

``create_file`` / ``read_file`` / ``present`` are PromptForge builtins.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import httpx

_DOCNUM_RE = re.compile(r"^[PN]\d{3,4}R\d+$", re.IGNORECASE)


def fetch_paper(paper: str) -> str:
    "Acquire a paper by file path, URL, or WG21 document number (e.g. P0870R8)."
    target = paper.strip()

    if Path(target).is_file():
        return Path(target).read_text(encoding="utf-8", errors="replace")

    if target.lower().startswith(("http://", "https://")):
        url = target
    elif _DOCNUM_RE.match(target):
        url = f"https://wg21.link/{target}"
    else:
        return (
            f"ACQUISITION FAILED: cannot resolve '{paper}' as a file, URL, "
            f"or WG21 document number"
        )

    try:
        response = httpx.get(url, follow_redirects=True, timeout=30.0)
    except httpx.HTTPError as exc:
        return f"ACQUISITION FAILED: {exc}"
    if response.status_code >= 400:
        return f"ACQUISITION FAILED: {url} returned HTTP {response.status_code}"

    body = response.text
    # WG21 papers are usually HTML; reduce to text so the model reads rationale,
    # not markup. Plain-text or markdown bodies pass through unchanged.
    return _html_to_text(body) if _looks_like_html(body) else body


def _looks_like_html(text: str) -> bool:
    head = text[:2000].lower()
    return "<html" in head or "<!doctype html" in head or "<body" in head


def _html_to_text(html: str) -> str:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def register_tools(runtime: Any) -> None:
    """Register PaperGate's domain tools, bound to the runtime's context."""
    ctx = runtime.ctx
    registry = runtime.registry

    def set_metadata(
        document: str,
        title: str,
        authors: str,
        classification: Literal["library", "language", "both"],
        tier: Literal["trivial", "small", "medium", "large", "massive"],
        tier_justification: str,
    ) -> str:
        "File the paper's identity and sizing."
        ctx.store.put("metadata", {
            "document": document,
            "title": title,
            "authors": authors,
            "classification": classification,
            "tier": tier,
            "tier_justification": tier_justification,
        })
        return f"metadata filed for {document}"

    def acquisition_failed(reason: str) -> str:
        "Record that the paper could not be acquired, and stop cleanly."
        ctx.store.put("metadata", {"status": f"ACQUISITION FAILED: {reason}"})
        return "acquisition failure recorded"

    def file_section(criterion: str, assessment: str) -> str:
        "Record that the paper addresses a criterion, with the prose assessment."
        ctx.store.add("sections", {"criterion": criterion, "assessment": assessment})
        return f"filed section: {criterion}"

    def file_missing(criterion: str, why: str) -> str:
        "Record that the paper does not address a criterion, and why it matters."
        ctx.store.add("missing", {"criterion": criterion, "why": why})
        return f"filed missing: {criterion}"

    def write_report(path: str) -> str:
        "Render the filed sections and the Missing paragraph into the report."
        # Metadata is filed in Digest's isolated store, so it reaches Evaluate as
        # the ``meta`` parameter, not in this section's store. Prefer whichever
        # is present.
        meta = ctx.store.get("metadata")
        if not meta and isinstance(ctx.params.get("meta"), dict):
            meta = ctx.params["meta"]
        report = _render_report(meta or {}, ctx.store)
        ctx.vfs.create(path, report)
        ctx.store.put("report_path", path)
        return f"wrote report to {path}"

    registry.register(fetch_paper)
    for fn in (set_metadata, acquisition_failed, file_section, file_missing, write_report):
        registry.register(fn)


def _render_report(meta: dict[str, Any], store: Any) -> str:
    """Assemble the report deterministically from filed state, no model tokens."""
    sections = store.get("sections", []) or []
    missing = store.get("missing", []) or []

    document = meta.get("document", "")
    title = meta.get("title", "")
    classification = meta.get("classification", "")
    tier = meta.get("tier", "")
    justification = meta.get("tier_justification", "")

    lines: list[str] = [f"# {document} {title}".strip(), ""]
    opening = (
        f"This paper is a {classification} proposal at {tier} tier. "
        f"{justification}".strip()
    )
    lines += [opening, ""]

    for section in sections:
        lines += [f"## {section['criterion']}", "", section["assessment"], ""]

    lines += ["## Missing From The Paper", ""]
    if missing:
        # Each item's reason is one sentence; normalize to a single trailing
        # period so the joined paragraph does not accumulate "..".
        lines.append(
            " ".join(
                f"{item['criterion']}: {item['why'].rstrip('.')}." for item in missing
            )
        )
    else:
        lines.append("The paper addresses the applicable criteria for its tier.")

    return "\n".join(lines).rstrip() + "\n"
