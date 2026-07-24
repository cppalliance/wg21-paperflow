#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Generic library tools available to every pipeline.

These operate on the runtime's ambient context (the current section's store is
swapped in by the runtime; the virtual filesystem is shared for the whole run).
A section only sees a tool if its Lua block scopes it in, so registering them
globally does not widen any section's tool set.

- ``create_file`` / ``append_file`` / ``read_file`` / ``delete_file`` operate on
  the virtual filesystem, never real disk.
- ``present`` records the operator-facing result on the run.
- ``ask_user`` surfaces a question through the runtime's ``ask_fn`` (or reports
  that the run is unattended).
"""

from __future__ import annotations

from typing import Any


def register_builtins(runtime: Any) -> None:
    """Register the generic library tools onto a runtime's registry."""
    ctx = runtime.ctx
    registry = runtime.registry

    def create_file(path: str, content: str) -> str:
        "Create or overwrite a virtual file. Returns a short confirmation."
        ctx.vfs.create(path, content)
        return f"wrote {path} ({len(content)} chars)"

    def append_file(path: str, content: str) -> str:
        "Append to a virtual file, creating it if absent."
        ctx.vfs.append(path, content)
        return f"appended {len(content)} chars to {path}"

    def read_file(path: str) -> str:
        "Return the contents of a virtual file."
        return ctx.vfs.read(path)

    def delete_file(path: str) -> str:
        "Delete a virtual file."
        ctx.vfs.delete(path)
        return f"deleted {path}"

    def present(summary: str, path: str = "") -> str:
        "Present the operator-facing result. Records it on the run."
        ctx.presented = summary
        if path:
            ctx.extras["presented_path"] = path
        return "presented"

    def ask_user(question: str) -> str:
        "Ask the operator a question and return the answer, if interactive."
        ask = ctx.extras.get("ask")
        if ask is None:
            return "No response available (unattended run)."
        return str(ask(question))

    for fn in (create_file, append_file, read_file, delete_file, present, ask_user):
        registry.register(fn)
