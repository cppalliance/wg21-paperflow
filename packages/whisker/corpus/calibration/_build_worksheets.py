# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# One-shot: export blind calibration worksheets (raw tomd markdown only).
# Safe to delete after use.

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from paperstore import SqliteBackend
from paperstore.errors import MissingPaperMdError

WORKSPACE = Path(r"C:\Users\sabo2\Desktop\cppalliance\data")
MANIFEST_PATH = Path(__file__).with_name("sample_manifest.json")
OUTPUT_DIR = Path(r"C:\Users\sabo2\Desktop\cppalliance\_scratch\whisker-g4-labeling\worksheets")
SUMMARY_PATH = Path(
    r"C:\Users\sabo2\Desktop\cppalliance\_scratch\whisker-g4-labeling\worksheets_manifest.json"
)


def load_pids() -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [entry["pid"] for entry in manifest["candidates"]]


def main() -> int:
    pids = load_pids()
    backend = SqliteBackend(WORKSPACE)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    failed: list[dict[str, str]] = []

    for pid in pids:
        try:
            markdown = backend.get_paper_md(pid)
        except MissingPaperMdError as exc:
            failed.append({"pid": pid, "reason": str(exc)})
            continue
        except Exception as exc:  # noqa: BLE001 — per-paper catch, do not abort batch
            failed.append({"pid": pid, "reason": f"{type(exc).__name__}: {exc}"})
            continue

        out_path = OUTPUT_DIR / f"{pid}.md"
        out_path.write_text(markdown, encoding="utf-8", newline="")
        written.append(pid)

    summary = {"written": written, "failed": failed}
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"total={len(pids)} written={len(written)} failed={len(failed)}", file=sys.stderr)
    for pid in written:
        print(f"OK {pid}", file=sys.stderr)
    for entry in failed:
        print(f"FAIL {entry['pid']}: {entry['reason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
