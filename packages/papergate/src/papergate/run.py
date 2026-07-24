#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Wire PaperGate onto the PromptForge runtime.

``build_runtime`` assembles the pipeline document, the domain tools, and a
model (or slot resolver) into a ready runtime. ``default_resolver`` reads the
pipeline's own ``## Services`` block and resolves it against the shared
SERVICES.toml so ``model("default")`` lands on a real RunPod endpoint.
``gate`` is the one-call entry point.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from promptforge.parser import Document
from promptforge.runtime import Runtime
from promptforge.services import ServiceResolver, load_services, parse_slot_map

from papergate.tools import register_tools

PAPERGATE_MD = Path(__file__).parent / "papergate.md"


def build_runtime(
    *,
    model: Any = None,
    resolver: Any = None,
    store: Any = None,
    vfs: Any = None,
    ask_fn: Any = None,
    max_turns: int = 40,
) -> Runtime:
    """Build a runtime for the PaperGate pipeline with its tools registered."""
    runtime = Runtime(
        str(PAPERGATE_MD),
        model=model,
        resolver=resolver,
        store=store,
        vfs=vfs,
        ask_fn=ask_fn,
        max_turns=max_turns,
    )
    register_tools(runtime)
    return runtime


def default_resolver(*, max_tokens: int = 8192) -> ServiceResolver:
    """Resolve the pipeline's ## Services slots against the shared SERVICES.toml."""
    document = Document.from_path(PAPERGATE_MD)
    slot_map = parse_slot_map(document.section("## Services").body)
    return ServiceResolver(load_services(), slot_map, max_tokens=max_tokens)


def gate(
    paper: str,
    *,
    output_path: str = "papergate.md",
    model: Any = None,
    resolver: Any = None,
) -> Any:
    """Gate one paper. Uses the default RunPod resolver unless one is supplied."""
    if model is None and resolver is None:
        resolver = default_resolver()
    runtime = build_runtime(model=model, resolver=resolver)
    return runtime.execute(params={"paper": paper, "output_path": output_path})
