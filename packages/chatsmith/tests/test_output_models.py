#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

import pytest
from chatsmith.models import TurnReply
from pydantic import ValidationError


def test_turn_reply_is_frozen_and_deeply_immutable() -> None:
    # The "LLM output is an immutable frozen model" invariant: a list input is
    # coerced to an immutable tuple, fields cannot be reassigned, and the model is
    # hashable (a mutable list field would leave it shallow-mutable and unhashable).
    reply = TurnReply(text="hi", topics=["a", "b"])
    assert reply.topics == ("a", "b")
    with pytest.raises(ValidationError):
        reply.text = "changed"
    assert isinstance(hash(reply), int)
