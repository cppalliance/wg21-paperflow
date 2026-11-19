#
# Copyright (c) 2026 Rob Beeston (rob@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Resolver for tomd's reading-judge requests (tomd.lib.pdf.judge).

tomd makes no model calls. Where its table readers disagree it lists judge
requests; this module answers them, from a per-paper cache first and, in live
mode, from a vision model shown the page crop and the readings. The answers go
back to tomd on a second conversion, which emits the picked readings.

The cache holds one answer per model and request id
(``"<model>/<id>": {"pick", "confidence", "why"}``). A request id hashes the
prompt version, the crop's page pieces and the readings, so a cached answer is
reused only for the same question: reruns cost nothing and give the same
markdown.
"""
from __future__ import annotations

import base64
import logging
from collections.abc import Callable, Mapping
from pathlib import Path

from tomd.lib.pdf.judge import LETTERS, prompt_text, render_crops

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
EFFORT = "medium"
MAX_TOKENS = 4096
MODES = ("off", "cache", "live")


def cache_key(model: str, req: Mapping) -> str:
    return f"{model}/{req['id']}"


class JudgeClient:
    """Asks the model to pick a reading. Credentials come from the environment, never logged."""

    def __init__(self, model: str = MODEL, effort: str = EFFORT, client=None):
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # live mode only: the cache mode needs no SDK
                raise RuntimeError("live table judging needs the 'anthropic' package installed") from exc
            client = anthropic.Anthropic()
        self.model, self.effort, self._client = model, effort, client

    def ask(self, images: list[bytes], req: Mapping) -> dict | None:
        """The answer for one request, or None when the model gives no usable one."""
        letters = list(LETTERS[:len(req["readings"])])
        content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                 "data": base64.standard_b64encode(png).decode("ascii")}}
                   for png in images]
        content.append({"type": "text", "text": prompt_text(req)})
        schema = {
            "type": "object",
            "properties": {
                "pick": {"type": "string", "enum": letters},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "why": {"type": "string"},
            },
            "required": ["pick", "confidence", "why"],
            "additionalProperties": False,
        }
        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
                messages=[{"role": "user", "content": content}],
            )
        except Exception as exc:  # one region keeps today's reading; the conversion goes on
            logger.warning("reading judge: request %s failed: %s", req["id"], type(exc).__name__)
            return None
        if msg.stop_reason != "end_turn":
            logger.warning("reading judge: request %s stopped: %s", req["id"], msg.stop_reason)
            return None
        text = "".join(b.text for b in msg.content if b.type == "text")
        return parse_answer(text, letters)


def parse_answer(text: str, letters: list[str]) -> dict | None:
    import json
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("pick") not in letters:
        return None
    if data.get("confidence") not in ("high", "medium", "low"):
        return None
    return {"pick": letters.index(data["pick"]), "confidence": data["confidence"],
            "why": str(data.get("why", ""))[:300]}


def resolve(source_path: Path, requests: list[Mapping], cache: dict,
            client: JudgeClient | None, model: str = MODEL) -> dict[str, dict]:
    """Answers keyed by request id: from ``cache``, else (live) from ``client``.

    New answers are added to ``cache``; the caller persists it.
    """
    answers: dict[str, dict] = {}
    doc = None
    try:
        for req in requests:
            key = cache_key(client.model if client else model, req)
            if key not in cache and client is not None:
                if doc is None:
                    import fitz
                    doc = fitz.open(str(source_path))
                ans = client.ask(render_crops(doc, req), req)
                if ans is not None:
                    cache[key] = ans
            if key in cache:
                answers[req["id"]] = cache[key]
    finally:
        if doc is not None:
            doc.close()
    return answers


def make_judge(mode: str, cache: dict | None, client: JudgeClient | None
               ) -> Callable[[Path, list[Mapping]], dict[str, dict]] | None:
    """The judge callable ``convert_one_paper`` takes, or None when judging is off."""
    if mode == "off" or cache is None:
        return None
    return lambda source_path, requests: resolve(source_path, requests, cache,
                                                 client if mode == "live" else None)
