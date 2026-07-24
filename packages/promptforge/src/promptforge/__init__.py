#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""PromptForge: a markdown-driven LLM pipeline runtime.

The markdown is the program, the model is the CPU, embedded Lua is the
microcode, and this package is the instruction decoder. A pipeline is a
set of named sections; the model transitions between them with a
context-clearing ``goto``, builds all state through flat tool calls into
a persistent store, and spawns subagents by section reference.

See ``promptforge.md`` for the full specification and ``DESIGN.md`` for
the architectural record kept during the build.
"""

from __future__ import annotations

__version__ = "0.4.1"

__all__ = ["__version__"]
