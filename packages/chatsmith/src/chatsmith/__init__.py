#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""chatsmith: a pack-driven knowledge-capture voice interviewer.

The package lands incrementally. This PR exposes the foundation and domain-pack
layer; the session store, LLM turn pipeline, Flask server, and CLI (adding
``Settings``, ``ChatbotService``, ``SessionStore``, ``build_store``, ``Agent``,
and ``StubAgent``) arrive in a follow-up PR and extend the re-exports below.
"""

from __future__ import annotations

from chatsmith.identity import Owner
from chatsmith.interview.models import InterviewSession, Turn
from chatsmith.models import NormalizeOutput, TurnReply
from chatsmith.pack import Branding, DomainPack
from chatsmith.pack import resolve as resolve_pack

__version__ = "0.1.0"

__all__ = [
    "Branding",
    "DomainPack",
    "InterviewSession",
    "NormalizeOutput",
    "Owner",
    "Turn",
    "TurnReply",
    "__version__",
    "resolve_pack",
]
