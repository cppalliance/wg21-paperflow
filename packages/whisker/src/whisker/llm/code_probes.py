#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""C10 identifier-line probes: live LLM checks that a model can address a fence.

The full tapetum run already judges every conversion axis (wording, code,
stable names, tables, xrefs, math, structure). This module is the
codeblock *instrumentation* lane, parallel to ``table_probes``: it does
not replace the axis judge. It asks the pod to locate a named identifier
on a stated fence line, then repeats the question against a corrupted
copy. Clean must recover the identifier. Corrupt must invert (NOT FOUND).
A corrupt control that does not invert leaves the probe unevaluated,
never passed.

Results are evidence, not certification. ``llm_readability`` stays LLM-free.

D1 exemption (inherited from readback / table_probes): calls the pod via
raw ``httpx``, not ``pipeline.run_agent``.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

import httpx

from whisker.det.llm_readability.models import CodeUnit

logger = logging.getLogger(__name__)

__all__ = [
    "CODE_PROBES_KIND",
    "CodeFenceProbeResult",
    "CodeProbesResult",
    "code_probes_to_dict",
    "corrupt_identifier_on_line",
    "pick_identifier_target",
    "run_code_probes",
    "score_corrupt_answer",
    "score_identifier_answer",
]

CODE_PROBES_KIND = "whisker-codeblock-identifier-probes"

# Cap live pod calls. Each fence needs a clean + corrupt pair.
CODE_PROBE_FENCE_CAP = 8

_REQUEST_TIMEOUT = 120.0
_MAX_ANSWER_TOKENS = 256
# Pod default flipped thinking-on; pin off for raw httpx probe calls.
_NON_THINK_CHAT_TEMPLATE_KWARGS: dict[str, object] = {"enable_thinking": False}

_IDENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z_0-9]{3,})\b")

_SKIP_IDENTS = frozenset({
    "auto",
    "bool",
    "class",
    "concept",
    "const",
    "consteval",
    "constexpr",
    "constinit",
    "define",
    "delete",
    "else",
    "endif",
    "enum",
    "false",
    "final",
    "ifdef",
    "ifndef",
    "include",
    "namespace",
    "nullptr",
    "override",
    "private",
    "protected",
    "public",
    "requires",
    "return",
    "static",
    "struct",
    "switch",
    "template",
    "this",
    "true",
    "typename",
    "union",
    "using",
    "virtual",
    "void",
    "volatile",
    "while",
})

_ABSENT_RE = re.compile(
    r"\b(not found|does not appear|not present|absent|no longer appears)\b",
    re.IGNORECASE,
)

_C10_SYSTEM = (
    "You are a document comprehension assistant. "
    "Treat each fenced block as one listing. "
    "Line numbers are 1-based inside the fence body and do not count "
    "the opening or closing fence markers. "
    "Answer with the identifier quoted exactly, or NOT FOUND. "
    "Be precise and concise."
)


@dataclass
class CodeFenceProbeResult:
    """Clean + corrupt identifier lookup for one fence."""

    unit_index: int
    identifier: str
    line: int
    first_line: str
    clean_question: str
    clean_answer: str
    clean_passed: bool
    corrupt_answer: str
    corrupt_inverted: bool
    passed: bool
    skipped: bool = False
    skip_reason: str = ""
    error: bool = False
    latency_ms: int = 0


@dataclass
class CodeProbesResult:
    """Identifier-line probes over the fences in one paper."""

    pid: str
    model: str
    units: list[CodeFenceProbeResult] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(
            1
            for item in self.units
            if item.passed and not item.error and not item.skipped
        )

    @property
    def fail_count(self) -> int:
        return sum(
            1
            for item in self.units
            if not item.passed and not item.error and not item.skipped
        )

    @property
    def skip_count(self) -> int:
        return sum(1 for item in self.units if item.skipped)


def code_probes_to_dict(result: CodeProbesResult) -> dict:
    """Serialize probes as evidence. Never a certification envelope."""
    return {
        "kind": CODE_PROBES_KIND,
        "pid": result.pid,
        "model": result.model,
        "units": [
            {
                "unit_index": item.unit_index,
                "identifier": item.identifier,
                "line": item.line,
                "first_line": item.first_line,
                "clean_question": item.clean_question,
                "clean_answer": item.clean_answer,
                "clean_passed": item.clean_passed,
                "corrupt_answer": item.corrupt_answer,
                "corrupt_inverted": item.corrupt_inverted,
                "passed": item.passed,
                "skipped": item.skipped,
                "skip_reason": item.skip_reason,
                "error": item.error,
                "latency_ms": item.latency_ms,
            }
            for item in result.units
        ],
        "pass_count": result.pass_count,
        "fail_count": result.fail_count,
        "skip_count": result.skip_count,
    }


def pick_identifier_target(unit: CodeUnit) -> tuple[int, str] | None:
    """Return ``(1-based line, identifier)`` for the first usable token."""
    for index, raw in enumerate(unit.body_lines):
        for match in _IDENT_RE.finditer(raw):
            ident = match.group(1)
            if ident in _SKIP_IDENTS:
                continue
            if ident.lower() in _SKIP_IDENTS:
                continue
            return index + 1, ident
    return None


def corrupt_identifier_on_line(unit: CodeUnit, line: int, ident: str) -> CodeUnit:
    """Reverse ``ident`` on the stated 1-based body line; leave others intact."""
    body = list(unit.body_lines)
    idx = line - 1
    if 0 <= idx < len(body):
        body[idx] = body[idx].replace(ident, ident[::-1], 1)
    return CodeUnit(
        index=unit.index,
        lang=unit.lang,
        body_lines=tuple(body),
        fence_style=unit.fence_style,
    )


def score_identifier_answer(answer: str, ident: str) -> bool:
    """Clean run: the original identifier must appear in the answer."""
    return ident.lower() in answer.lower()


def score_corrupt_answer(answer: str, ident: str) -> bool:
    """Corrupt run must invert: NOT FOUND, or the original ident is gone."""
    if _ABSENT_RE.search(answer):
        return True
    return ident.lower() not in answer.lower()


def _render_fence(unit: CodeUnit) -> str:
    fence = "```" if unit.fence_style == "backtick" else "~~~"
    opener = f"{fence}{unit.lang}" if unit.lang else fence
    return "\n".join((opener, *unit.body_lines, fence))


def _first_line(unit: CodeUnit) -> str:
    for line in unit.body_lines:
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _question(unit: CodeUnit, line: int, ident: str) -> str:
    start = _first_line(unit) or f"fence {unit.index + 1}"
    return (
        f"In the fenced block that starts with {start!r}, does line {line} "
        f"contain the identifier {ident!r}? Quote it exactly if present, "
        f"otherwise answer NOT FOUND."
    )


def _ask_pod(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    fence_md: str,
    question: str,
    system_prompt: str,
) -> tuple[str, int]:
    t0 = time.monotonic()
    resp = client.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"FENCE:\n{fence_md}\n\nQUESTION:\n{question}",
                },
            ],
            "max_tokens": _MAX_ANSWER_TOKENS,
            "temperature": 0.0,
            "chat_template_kwargs": _NON_THINK_CHAT_TEMPLATE_KWARGS,
        },
        timeout=_REQUEST_TIMEOUT,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        return "(no response)", latency_ms
    answer = choices[0].get("message", {}).get("content") or ""
    if not isinstance(answer, str):
        answer = ""
    return answer.strip(), latency_ms


def run_code_probes(
    pid: str,
    units: tuple[CodeUnit, ...],
    *,
    base_url: str,
    api_key: str,
    model: str = "deepseek-v4-pro",
    system_prompt: str | None = None,
) -> CodeProbesResult:
    """Probe eligible fences. Results are evidence, not certification."""
    result = CodeProbesResult(pid=pid, model=model)
    eligible = [unit for unit in units if pick_identifier_target(unit)]
    if not eligible:
        return result

    system = system_prompt if system_prompt is not None else _C10_SYSTEM

    with httpx.Client() as client:
        for unit in eligible[:CODE_PROBE_FENCE_CAP]:
            target = pick_identifier_target(unit)
            if target is None:
                continue
            line, ident = target
            question = _question(unit, line, ident)
            clean_md = _render_fence(unit)
            corrupt_md = _render_fence(
                corrupt_identifier_on_line(unit, line, ident)
            )
            error = False
            latency = 0
            try:
                clean_answer, clean_ms = _ask_pod(
                    client, base_url, api_key, model, clean_md, question, system
                )
                corrupt_answer, corrupt_ms = _ask_pod(
                    client, base_url, api_key, model, corrupt_md, question, system
                )
                latency = clean_ms + corrupt_ms
            except (httpx.HTTPError, KeyError) as exc:
                clean_answer = f"(transport error: {type(exc).__name__}: {exc})"
                corrupt_answer = ""
                error = True

            if error:
                result.units.append(
                    CodeFenceProbeResult(
                        unit_index=unit.index,
                        identifier=ident,
                        line=line,
                        first_line=_first_line(unit),
                        clean_question=question,
                        clean_answer=clean_answer,
                        clean_passed=False,
                        corrupt_answer=corrupt_answer,
                        corrupt_inverted=False,
                        passed=False,
                        error=True,
                        latency_ms=latency,
                    )
                )
                continue

            clean_ok = score_identifier_answer(clean_answer, ident)
            corrupt_ok = score_corrupt_answer(corrupt_answer, ident)
            if clean_ok and not corrupt_ok:
                result.units.append(
                    CodeFenceProbeResult(
                        unit_index=unit.index,
                        identifier=ident,
                        line=line,
                        first_line=_first_line(unit),
                        clean_question=question,
                        clean_answer=clean_answer,
                        clean_passed=True,
                        corrupt_answer=corrupt_answer,
                        corrupt_inverted=False,
                        passed=False,
                        skipped=True,
                        skip_reason="corrupt control did not invert",
                        latency_ms=latency,
                    )
                )
                continue

            result.units.append(
                CodeFenceProbeResult(
                    unit_index=unit.index,
                    identifier=ident,
                    line=line,
                    first_line=_first_line(unit),
                    clean_question=question,
                    clean_answer=clean_answer,
                    clean_passed=clean_ok,
                    corrupt_answer=corrupt_answer,
                    corrupt_inverted=corrupt_ok,
                    passed=clean_ok and corrupt_ok,
                    latency_ms=latency,
                )
            )
    return result
