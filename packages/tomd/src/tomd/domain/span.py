"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import ClassVar, Literal, Self


@dataclass(frozen=True)
class Span:
    """Base class for all semantic inline text nodes."""

    wording_role: ClassVar[Literal["ins", "del"] | None] = None

    @property
    def text(self) -> str:
        """Return recursive unformatted plain text of this span."""
        return ""

    def map_text(self, fn: Callable[[str], str]) -> Self:
        """Return a copy of this span with ``fn`` applied to plain text leaves."""
        return self

    def role_text(self, target_type: type["Span"]) -> str:
        """Return concatenated plain text of spans matching ``target_type``."""
        return ""

    def unwrap(self, target_type: type["Span"]) -> tuple["Span", ...]:
        """Return span sequence with ``target_type`` containers replaced by their children."""
        return (self,)


@dataclass(frozen=True)
class TextSpan(Span):
    """Plain unformatted text leaf."""

    content: str

    @property
    def text(self) -> str:
        return self.content

    def map_text(self, fn: Callable[[str], str]) -> Self:
        return replace(self, content=fn(self.content))


@dataclass(frozen=True)
class CodeSpan(Span):
    """Inline code snippet leaf."""

    code: str

    @property
    def text(self) -> str:
        return self.code


@dataclass(frozen=True)
class LineBreakSpan(Span):
    """Hard line break within a block or table cell."""

    @property
    def text(self) -> str:
        return "\n"


@dataclass(frozen=True)
class ContainerSpan(Span):
    """Base class for semantic inline spans that wrap child spans."""

    children: tuple[Span, ...] = field(default_factory=tuple)

    @classmethod
    def from_text(cls, text: str) -> Self:
        return cls(children=(TextSpan(text),))

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.children)

    def map_text(self, fn: Callable[[str], str]) -> Self:
        return replace(self, children=tuple(c.map_text(fn) for c in self.children))

    def role_text(self, target_type: type[Span]) -> str:
        if isinstance(self, target_type):
            return self.text
        return "".join(c.role_text(target_type) for c in self.children)

    def unwrap(self, target_type: type[Span]) -> tuple[Span, ...]:
        unwrapped = tuple(u for c in self.children for u in c.unwrap(target_type))
        if isinstance(self, target_type):
            return unwrapped
        return (replace(self, children=unwrapped),)


@dataclass(frozen=True)
class StrongSpan(ContainerSpan):
    """Strongly emphasized inline text container."""


@dataclass(frozen=True)
class EmphasisSpan(ContainerSpan):
    """Emphasized inline text container."""


@dataclass(frozen=True)
class DeletedSpan(ContainerSpan):
    """Deleted wording text container."""

    wording_role: ClassVar[Literal["ins", "del"] | None] = "del"


@dataclass(frozen=True)
class InsertedSpan(ContainerSpan):
    """Inserted wording text container."""

    wording_role: ClassVar[Literal["ins", "del"] | None] = "ins"


@dataclass(frozen=True)
class SubscriptSpan(ContainerSpan):
    """Subscript inline text container."""


@dataclass(frozen=True)
class SuperscriptSpan(ContainerSpan):
    """Superscript inline text container."""


@dataclass(frozen=True)
class LinkSpan(ContainerSpan):
    """Hyperlinked inline text pointing to a target URL."""

    url: str = ""
    title: str | None = None

    @classmethod
    def from_text(
        cls,
        text: str,
        url: str = "",
        title: str | None = None,
    ) -> "LinkSpan":
        return cls(children=(TextSpan(text),), url=url, title=title)
