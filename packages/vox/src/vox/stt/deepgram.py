#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Deepgram speech-to-text with optional keyterm boosting.

Prerecorded (buffer the whole utterance, one call). Requires the ``deepgram``
extra and a Deepgram API key. Keyterms are supplied by the caller (e.g. a domain
glossary), so this adapter stays domain-neutral.
"""

from __future__ import annotations

from typing import Any


class DeepgramStt:
    def __init__(
        self,
        api_key: str,
        model: str = "nova-3",
        keyterms: list[str] | None = None,
        *,
        keyterm_limit: int = 100,
    ):
        from deepgram import DeepgramClient  # pyright: ignore[reportMissingImports]

        self._client = DeepgramClient(api_key=api_key)
        self._model = model
        # Deepgram accepts a bounded keyterm set; keep the highest-priority terms.
        self._keyterms = list(keyterms or [])[:keyterm_limit]

    def transcribe(self, audio: bytes, content_type: str) -> str:
        response = self._client.listen.v1.media.transcribe_file(
            request=audio,
            model=self._model,
            smart_format=True,
            keyterm=self._keyterms or None,
        )
        return _extract_transcript(response)


def _extract_transcript(response: Any) -> str:
    """Pull the best transcript from a Deepgram response (pydantic model or dict)."""
    if hasattr(response, "model_dump"):
        data = response.model_dump()
    elif hasattr(response, "to_dict"):
        data = response.to_dict()
    else:
        data = response
    try:
        alt = data["results"]["channels"][0]["alternatives"][0]
        return (alt.get("transcript") or "").strip()
    except (KeyError, IndexError, TypeError):
        return ""
