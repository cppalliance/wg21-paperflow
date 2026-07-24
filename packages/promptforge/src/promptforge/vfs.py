#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""An in-memory virtual filesystem.

The model believes it is writing files; the runtime holds a dict keyed by
path. Virtual files are scoped to the run and discarded at the end. A section
given only virtual-file tools has no real path to traverse and no
exfiltration channel, which is a deliberate part of the capability sandbox.

Promoting a chosen file to real disk is the caller's job (one audited
chokepoint), never a tool the model can reach directly.
"""

from __future__ import annotations

import fnmatch


class MemVFS:
    """A path-keyed store of in-memory file blobs."""

    def __init__(self) -> None:
        self._files: dict[str, str] = {}

    def create(self, path: str, content: str) -> None:
        """Create or overwrite a file."""
        self._files[path] = content

    def append(self, path: str, content: str) -> None:
        """Append to a file, creating it if absent."""
        self._files[path] = self._files.get(path, "") + content

    def read(self, path: str) -> str:
        try:
            return self._files[path]
        except KeyError:
            raise FileNotFoundError(path) from None

    def delete(self, path: str) -> None:
        try:
            del self._files[path]
        except KeyError:
            raise FileNotFoundError(path) from None

    def exists(self, path: str) -> bool:
        return path in self._files

    def glob(self, pattern: str) -> list[str]:
        """Return sorted paths matching a shell-style glob (e.g. ``s-*.md``)."""
        return sorted(p for p in self._files if fnmatch.fnmatch(p, pattern))

    def paths(self) -> list[str]:
        return list(self._files)
