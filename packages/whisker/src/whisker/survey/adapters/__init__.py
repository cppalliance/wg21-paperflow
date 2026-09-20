#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Competitor adapters for the survey monitor. One module per project."""

from whisker.survey.adapters.contract import (
    REQUIRED_ATTRS,
    AdapterContractError,
    load_adapter,
)

__all__ = ["REQUIRED_ATTRS", "AdapterContractError", "load_adapter"]
