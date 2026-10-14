#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# G4 Rater A: alliance-pod (deepseek-v4-pro), blind, independent judgment.
# One-shot calibration-labeling script. Safe to delete after use.
#
# Reads the 34-candidate sample manifest, plus the blind worksheet markdown
# and extracted source text staged under _scratch/whisker-g4-labeling/ by a
# separate step, calls alliance-pod once per candidate with ONLY the
# candidate markdown + source text (never whisker's own score/verdict, per
# PROTOCOL.md Section 4's blindness rule), and asks for a single
# pass/review/fail content-fidelity judgment (PROTOCOL.md Section 3's
# rubric). Writes one raw+parsed JSON file per PID plus a combined summary.

from __future__ import annotations

import json
import re
import sys
import time
import traceback
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[4]
MANIFEST_PATH = Path(__file__).with_name("sample_manifest.json")
WORKSHEETS_DIR = REPO_ROOT / "_scratch" / "whisker-g4-labeling" / "worksheets"
SOURCES_DIR = REPO_ROOT / "_scratch" / "whisker-g4-labeling" / "sources"
OUT_DIR = REPO_ROOT / "_scratch" / "whisker-g4-labeling" / "rater_a_deepseek"
ENV_PATH = REPO_ROOT / ".env"

BASE_URL = "https://sgjy18glyi4blu-8000.proxy.runpod.net/v1"
MODEL = "deepseek-v4-pro"
REQUEST_TIMEOUT = 240.0
MAX_TOKENS = 1024
MAX_RETRIES = 3
RETRY_BACKOFF_S = 5.0

# deepseek-v4-pro's real context window is 393216 tokens (SERVICES.toml,
# chars_per_token=4.0 -> ~1.57M chars). A first pass used a 60_000-char cap
# per side and produced a CONTAMINATED "fail" label on P3045R7: the rater
# correctly reported "candidate is severely truncated", quoting our own
# "[TRUNCATED FOR LENGTH]" marker verbatim -- that is our pipeline's
# truncation, not tomd's. Raised generously so only genuine multi-MB source
# outliers still truncate (recorded via candidate_truncated/source_truncated
# on every entry so a contaminated label is never silently trusted).
MAX_SOURCE_CHARS = 450_000
MAX_CANDIDATE_CHARS = 450_000

_SYSTEM_PROMPT = (
    "You are a CONTENT-COVERAGE auditor for a PDF/HTML-to-Markdown converter "
    "pipeline. You will see a SOURCE document and a CANDIDATE markdown "
    "conversion of that same document. Your label will be validated against "
    "a mechanical UNIGRAM (bag-of-words) RECALL score: the fraction of "
    "distinct words from the source that appear ANYWHERE in the candidate, "
    "regardless of order, position, or grouping. You must judge the SAME "
    "thing that metric measures, and NOTHING else.\n\n"
    "CRITICAL DISTINCTION, read carefully:\n"
    "- STRUCTURAL corruption (a table's rows get merged into one paragraph, "
    "headings are dropped or renumbered, list markers vanish, multiple "
    "sections run together into a wall of text, HTML tags leak into the "
    "text) is NOT content loss BY ITSELF, as long as the actual words, "
    "numbers, and names that were in the source are still present "
    "SOMEWHERE in the candidate, in any order. A word-level bag-of-words "
    "score cannot see structure at all, so you must not either. Label "
    "these 'pass' unless you can also point to specific words/numbers/"
    "names that are truly ABSENT, not just reordered or unstructured.\n"
    "- CONTENT loss (a sentence, paragraph, table cell's actual text, a "
    "reference entry, a code line, an author name, a number) is present in "
    "the SOURCE but you cannot find it ANYWHERE in the CANDIDATE, in any "
    "form, even garbled/merged. THIS is what you are rating.\n\n"
    "Worked example: source table row 'P1063R0 | Jane Doe | adds "
    "constexpr support' becomes candidate text '...P1063R0 Jane Doe adds "
    "constexpr support P1134R0 John Smith fixes...' (rows merged into a "
    "run-on paragraph, no columns, no table markup) -> STILL 'pass': every "
    "word survived, just unstructured. It would only become 'fail' if, "
    "say, 'P1063R0' or 'Jane Doe' or 'constexpr support' were nowhere to "
    "be found in the candidate at all.\n\n"
    "Ignore ALL cosmetic differences: heading punctuation, list marker "
    "style, whitespace, code fence language tags, HTML vs markdown table "
    "syntax, paragraph vs run-on-text layout.\n\n"
    "Respond with ONLY a single JSON object, no other text, no markdown "
    "fences, matching exactly this shape: "
    '{"label": "pass"|"review"|"fail", "reasoning": "<one or two '
    "sentences naming the SPECIFIC words/sentences/data you checked are "
    'truly absent, not just unstructured>"}. '
    '"pass" = no meaningful WORD-LEVEL content loss (structural mess is '
    'fine). "review" = some specific content genuinely missing or you are '
    'unsure it survived anywhere in the candidate. "fail" = clear, '
    "substantial word-level content loss you can point to concrete "
    "missing terms/passages for (not just messy structure)."
)


def _load_key() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("ALLIANCE_POD_KEY"):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError(f"ALLIANCE_POD_KEY not found in {ENV_PATH}")


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n\n... [TRUNCATED FOR LENGTH] ...", True


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    # Strip a leading <think>...</think> block some vllm_thinking backends
    # prepend even when not requested in the visible content.
    raw = re.sub(r"^<think>.*?</think>\s*", "", raw, flags=re.DOTALL)
    # Strip markdown code fences if the model wrapped the JSON anyway.
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object found in response: {raw[:300]!r}")
    return json.loads(match.group(0))


def _rate_one(
    client: httpx.Client, api_key: str, pid: str, candidate_md: str, source_text: str
) -> dict:
    candidate_trunc, candidate_was_truncated = _truncate(candidate_md, MAX_CANDIDATE_CHARS)
    source_trunc, source_was_truncated = _truncate(source_text, MAX_SOURCE_CHARS)

    user_content = (
        f"SOURCE DOCUMENT (raw, may be PDF text-layer or HTML):\n{source_trunc}\n\n"
        f"---\n\nCANDIDATE MARKDOWN (the conversion to judge):\n{candidate_trunc}"
    )

    t0 = time.monotonic()
    last_exc: Exception | None = None
    resp = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": MAX_TOKENS,
                    "temperature": 0.0,
                },
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            break
        except httpx.HTTPError as exc:
            last_exc = exc
            resp = None
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_S * attempt)
    if resp is None:
        assert last_exc is not None
        raise last_exc
    latency_ms = int((time.monotonic() - t0) * 1000)
    data = resp.json()
    choices = data.get("choices", [])
    content = choices[0].get("message", {}).get("content", "") if choices else ""

    entry: dict = {
        "pid": pid,
        "rater": "alliance-pod:deepseek-v4-pro",
        "latency_ms": latency_ms,
        "raw_content": content,
        "candidate_truncated": candidate_was_truncated,
        "source_truncated": source_was_truncated,
    }
    try:
        parsed = _extract_json(content)
        label = str(parsed.get("label", "")).strip().lower()
        if label not in ("pass", "review", "fail"):
            raise ValueError(f"unexpected label value: {label!r}")
        entry["label"] = label
        entry["reasoning"] = parsed.get("reasoning", "")
        entry["parse_error"] = None
    except Exception as exc:  # noqa: BLE001 -- per-item catch, report and continue
        entry["label"] = None
        entry["reasoning"] = None
        entry["parse_error"] = f"{type(exc).__name__}: {exc}"
    return entry


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pids = [c["pid"] for c in manifest["candidates"]]

    api_key = _load_key()
    results: list[dict] = []
    errors: list[dict] = []

    with httpx.Client() as client:
        for i, pid in enumerate(pids, 1):
            ws_path = WORKSHEETS_DIR / f"{pid}.md"
            src_path = SOURCES_DIR / f"{pid}.txt"
            if not ws_path.exists() or not src_path.exists():
                errors.append({"pid": pid, "reason": "missing worksheet or source file"})
                print(f"[{i}/{len(pids)}] {pid}: SKIP (missing input file)", file=sys.stderr)
                continue
            candidate_md = ws_path.read_text(encoding="utf-8", errors="replace")
            source_text = src_path.read_text(encoding="utf-8", errors="replace")
            try:
                entry = _rate_one(client, api_key, pid, candidate_md, source_text)
            except Exception as exc:  # noqa: BLE001 -- per-paper catch, do not abort batch
                errors.append({"pid": pid, "reason": f"{type(exc).__name__}: {exc}"})
                print(f"[{i}/{len(pids)}] {pid}: ERROR {exc}", file=sys.stderr)
                continue
            results.append(entry)
            (OUT_DIR / f"{pid}.json").write_text(
                json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(
                f"[{i}/{len(pids)}] {pid}: label={entry['label']} "
                f"({entry['latency_ms']}ms)",
                file=sys.stderr,
            )

    summary_path = OUT_DIR / "_summary.json"
    summary_path.write_text(
        json.dumps({"results": results, "errors": errors}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"rated={len(results)} errors={len(errors)}", file=sys.stderr)
    return 0 if not errors else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
