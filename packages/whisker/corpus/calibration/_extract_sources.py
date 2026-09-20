# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# One-shot: extract raw source text for calibration sample PIDs.
# Safe to delete after use.

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from paperstore import SqliteBackend
from whisker.llm.textlayer import TextLayerError, extract_textlayer

WORKSPACE = Path(r"C:\Users\sabo2\Desktop\cppalliance\data")
MANIFEST_PATH = Path(__file__).with_name("sample_manifest.json")
OUT_DIR = Path(r"C:\Users\sabo2\Desktop\cppalliance\_scratch\whisker-g4-labeling\sources")
SUMMARY_PATH = OUT_DIR.parent / "sources_manifest.json"
PAGE_BREAK = "\n\n--- PAGE BREAK ---\n\n"


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pids = [c["pid"] for c in manifest["candidates"]]
    if len(pids) != 34:
        print(f"expected 34 candidates, got {len(pids)}", file=sys.stderr)

    backend = SqliteBackend(WORKSPACE)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, object]] = []
    failed: list[dict[str, str]] = []

    for pid in pids:
        pid_lower = pid.lower()
        try:
            source_path = backend.get_source_path(pid_lower)
        except Exception as exc:  # noqa: BLE001 — per-paper catch, do not abort batch
            failed.append({"pid": pid, "reason": f"get_source_path: {type(exc).__name__}: {exc}"})
            continue

        if not source_path.exists():
            failed.append({"pid": pid, "reason": f"source missing: {source_path}"})
            continue

        suffix = source_path.suffix.lower()
        try:
            if suffix == ".pdf":
                pages = extract_textlayer(source_path)
                text = PAGE_BREAK.join(pages)
                source_type = "pdf"
            elif suffix in (".html", ".htm"):
                text = source_path.read_text(encoding="utf-8", errors="replace")
                source_type = "html"
            else:
                failed.append({"pid": pid, "reason": f"unsupported source suffix: {suffix}"})
                continue
        except TextLayerError as exc:
            failed.append({"pid": pid, "reason": f"TextLayerError: {exc}"})
            continue
        except Exception as exc:  # noqa: BLE001 — per-paper catch, do not abort batch
            failed.append({"pid": pid, "reason": f"{type(exc).__name__}: {exc}"})
            continue

        out_path = OUT_DIR / f"{pid}.txt"
        out_path.write_text(text, encoding="utf-8")
        written.append({"pid": pid, "source_type": source_type, "chars": len(text)})
        print(f"ok {pid} {source_type} chars={len(text)}", file=sys.stderr)

    summary = {"written": written, "failed": failed}
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    pdf_count = sum(1 for w in written if w["source_type"] == "pdf")
    html_count = sum(1 for w in written if w["source_type"] == "html")
    print(
        f"done written={len(written)} pdf={pdf_count} html={html_count} failed={len(failed)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
