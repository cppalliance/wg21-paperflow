#
# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Resolver for tomd's page-table requests (tomd.lib.pdf.page_tables).

tomd makes no model calls. It lists one request per page; this module answers
them, from a per-paper cache first and, in live mode, from a vision model shown
the page image, which writes out the tables on it. tomd keeps only the page's
own words from those answers, and adds a table only where it selected none.

The cache holds one answer per model and request id
(``"<model>/<id>": {"tables": [...]}``). A request id hashes the prompt version
and the page image, so reruns cost nothing and give the same markdown.
"""
from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable
from pathlib import Path

from tomd.lib.pdf.page_tables import INSTRUCTIONS, SCHEMA, page_table_requests, render_page

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
EFFORT = "medium"
MAX_TOKENS = 32000
MODES = ("off", "cache", "live")


def cache_key(model: str, req_id: str) -> str:
    return f"{model}/{req_id}"


class PageTablesClient:
    """Asks the model for the tables on one page. Credentials come from the environment, never logged."""

    def __init__(self, model: str = MODEL, effort: str = EFFORT, client=None):
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # live mode only: the cache mode needs no SDK
                raise RuntimeError("live page tables need the 'anthropic' package installed") from exc
            client = anthropic.Anthropic(max_retries=4)
        self.model, self.effort, self._client = model, effort, client

    def ask(self, png: bytes) -> dict | None:
        """The answer for one page image, or None when the model gives no usable one."""
        content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                 "data": base64.standard_b64encode(png).decode("ascii")}},
                   {"type": "text", "text": INSTRUCTIONS}]
        try:
            # streamed: a page of dense tables can take long to write out
            with self._client.messages.stream(
                model=self.model,
                max_tokens=MAX_TOKENS,
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[{"role": "user", "content": content}],
            ) as stream:
                msg = stream.get_final_message()
        except Exception as exc:  # one page adds no tables; the conversion goes on
            logger.warning("page tables: request failed: %s", type(exc).__name__)
            return None
        if msg.stop_reason != "end_turn":
            logger.warning("page tables: request stopped: %s", msg.stop_reason)
            return None
        return parse_answer("".join(b.text for b in msg.content if b.type == "text"))


def parse_answer(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("tables"), list):
        return None
    return {"tables": data["tables"]}


def resolve(source_path: Path, cache: dict, client: PageTablesClient | None,
            model: str = MODEL) -> dict[str, dict]:
    """Answers keyed by page request id: from ``cache``, else (live) from ``client``.

    New answers are added to ``cache``; the caller persists it.
    """
    import fitz
    answers: dict[str, dict] = {}
    with fitz.open(str(source_path)) as doc:
        for req in page_table_requests(doc):
            key = cache_key(client.model if client else model, req["id"])
            if key not in cache and client is not None:
                ans = client.ask(render_page(doc[req["page"]]))
                if ans is not None:
                    cache[key] = ans
            if key in cache:
                answers[req["id"]] = cache[key]
    return answers


def make_page_tables(mode: str, cache: dict | None, client: PageTablesClient | None
                     ) -> Callable[[Path], dict[str, dict]] | None:
    """The page-tables callable ``convert_one_paper`` takes, or None when off."""
    if mode == "off" or cache is None:
        return None
    return lambda source_path: resolve(source_path, cache, client if mode == "live" else None)
