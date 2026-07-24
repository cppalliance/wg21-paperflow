#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""End-to-end scripted runs of design Examples 1 (goto) and 3 (fan-out).

These exercise the whole stack (parser, lua, execute, runtime) against a
scripted model, with no live endpoint, so they are fully deterministic.
"""

from __future__ import annotations

from promptforge.inference import ScriptedModel, tool_call, turn
from promptforge.runtime import Runtime

EXAMPLE_1 = '''## Main

You classify a document. Read it, then hand off to the classifier.

```lua
tools.add("read_input", "goto", "done")
```

1. Call read_input to load the document.
2. Call goto("## Classify").

## Classify

Decide the document's type: library, language, both, or other.

```lua
tools.add("get_input", "set_classification", "done")
function check()
  assert(store.exists("classification"), "no classification was filed")
end
```
'''

EXAMPLE_3 = '''## Main

Extract structured items from every chunk of the paper.

```lua
tools.add("chunk_paper", "goto", "done")
```

1. Call chunk_paper to split the paper into chunks.
2. Call goto("## ExtractAll").

## ExtractAll

```lua
local chunks = store.get("chunk_ids")
local tasks = {}
for _, cid in ipairs(chunks) do
  tasks[#tasks + 1] = { section = "## Extract", params = { chunk_id = cid } }
end
fanout(tasks, {})
```

## Extract

Extract every claim from this one chunk. Call done when the chunk is exhausted.

```lua
tools.add("read_chunk", "add_claim", "done")
function check()
  assert(store.count("items", { chunk = params.chunk_id }) > 0,
         "chunk produced no items")
end
```
'''


def test_example_1_minimal_classifier() -> None:
    model = ScriptedModel([
        turn(
            tool_call("read_input", path="p1234.md"),
            tool_call("goto", section="## Classify"),
        ),
        turn(
            tool_call("get_input"),
            tool_call("set_classification", type="library", confidence="high"),
            tool_call("done"),
        ),
    ])
    runtime = Runtime(EXAMPLE_1, model=model)

    def read_input(path: str) -> str:
        runtime.ctx.store.put("input", f"<document at {path}>")
        return "loaded"

    def get_input() -> str:
        return runtime.ctx.store.get("input", "")

    def set_classification(type: str, confidence: str) -> str:
        runtime.ctx.store.put("classification", {"type": type, "confidence": confidence})
        return "filed"

    for fn in (read_input, get_input, set_classification):
        runtime.registry.register(fn)

    result = runtime.execute()
    assert result.ok
    assert runtime.store.get("classification")["type"] == "library"


def test_example_3_fanout_covers_every_chunk() -> None:
    # Main splits into 3 chunks; ExtractAll fans out one Extract per chunk.
    model = ScriptedModel([
        turn(tool_call("chunk_paper"), tool_call("goto", section="## ExtractAll")),
        turn(tool_call("read_chunk", chunk_id=0), tool_call("add_claim", chunk=0, quote="a", line=1), tool_call("done")),
        turn(tool_call("read_chunk", chunk_id=1), tool_call("add_claim", chunk=1, quote="b", line=2), tool_call("done")),
        turn(tool_call("read_chunk", chunk_id=2), tool_call("add_claim", chunk=2, quote="c", line=3), tool_call("done")),
    ])
    runtime = Runtime(EXAMPLE_3, model=model)

    def chunk_paper() -> str:
        runtime.ctx.store.put("chunk_ids", [0, 1, 2])
        return "3 chunks"

    def read_chunk(chunk_id: int) -> str:
        return f"<text of chunk {chunk_id}>"

    def add_claim(chunk: int, quote: str, line: int) -> str:
        runtime.ctx.store.add("items", {"chunk": chunk, "quote": quote, "line": line})
        return "claim filed"

    for fn in (chunk_paper, read_chunk, add_claim):
        runtime.registry.register(fn)

    result = runtime.execute()
    assert result.ok
    chunks_with_items = {item["chunk"] for item in runtime.store.get("items")}
    assert chunks_with_items == {0, 1, 2}
