"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Span:
    """Base class for all semantic inline text nodes."""

    @property
    def text(self) -> str:
        """Return recursive unformatted plain text of this span."""
        return ""


@dataclass(frozen=True)
class TextSpan(Span):
    """Plain unformatted text leaf."""

    content: str

    @property
    def text(self) -> str:
        return self.content


@dataclass(frozen=True)
class CodeSpan(Span):
    """Monospace inline code snippet leaf (e.g. `std::vector`)."""

    code: str

    @property
    def text(self) -> str:
        return self.code


@dataclass(frozen=True)
class LineBreakSpan(Span):
    """Hard line break within a block or table cell (<br>)."""

    @property
    def text(self) -> str:
        return "\n"


@dataclass(frozen=True)
class StrongSpan(Span):
    """Bold / strongly emphasized text container (e.g. **important**)."""

    children: tuple[Span, ...] = field(default_factory=tuple)

    @classmethod
    def from_text(cls, text: str) -> "StrongSpan":
        return cls(children=(TextSpan(text),))

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.children)


@dataclass(frozen=True)
class EmphasisSpan(Span):
    """Italic / emphasized text container (e.g. *note*)."""

    children: tuple[Span, ...] = field(default_factory=tuple)

    @classmethod
    def from_text(cls, text: str) -> "EmphasisSpan":
        return cls(children=(TextSpan(text),))

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.children)


@dataclass(frozen=True)
class StrikethroughSpan(Span):
    """Deleted wording edit / strikethrough container (e.g. <del>)."""

    children: tuple[Span, ...] = field(default_factory=tuple)

    @classmethod
    def from_text(cls, text: str) -> "StrikethroughSpan":
        return cls(children=(TextSpan(text),))

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.children)


@dataclass(frozen=True)
class UnderlineSpan(Span):
    """Inserted wording edit / underline container (e.g. <ins>)."""

    children: tuple[Span, ...] = field(default_factory=tuple)

    @classmethod
    def from_text(cls, text: str) -> "UnderlineSpan":
        return cls(children=(TextSpan(text),))

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.children)


@dataclass(frozen=True)
class SubscriptSpan(Span):
    """Subscript inline container (e.g. <sub>)."""

    children: tuple[Span, ...] = field(default_factory=tuple)

    @classmethod
    def from_text(cls, text: str) -> "SubscriptSpan":
        return cls(children=(TextSpan(text),))

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.children)


@dataclass(frozen=True)
class SuperscriptSpan(Span):
    """Superscript inline container (e.g. <sup>)."""

    children: tuple[Span, ...] = field(default_factory=tuple)

    @classmethod
    def from_text(cls, text: str) -> "SuperscriptSpan":
        return cls(children=(TextSpan(text),))

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.children)


@dataclass(frozen=True)
class LinkSpan(Span):
    """Hyperlinked inline text pointing to a target URL."""

    children: tuple[Span, ...] = field(default_factory=tuple)
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

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.children)
