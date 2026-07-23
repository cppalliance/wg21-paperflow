#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Agora paper-domain errors.

User-fixable errors raised while preparing a paper for the agora
pipeline. Both inherit ``pipeline.PipelineError`` so downstream
handlers can catch the whole pipeline error family uniformly.
"""

from __future__ import annotations

from pipeline.errors import PipelineError


class PaperNotFoundError(PipelineError):
    """Paper not in paperstore.

    Message includes the paperflow command to run.
    """


class PaperNotConvertedError(PipelineError):
    """Paper has no converted markdown.

    Message includes the paperflow convert command.
    """
