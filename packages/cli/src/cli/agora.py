#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""CLI command module for 'paperflow agora'."""

from __future__ import annotations

from cli._process import run_process_command


def command(args, backend):
    return run_process_command(args, backend, through=5)
