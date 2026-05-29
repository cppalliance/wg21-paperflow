"""Simulate the _join_cross_page fix: compare old vs new on all PDFs."""
import sys
import io
import re
from pathlib import Path
from dataclasses import replace

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent / "packages" / "tomd" / "src"))

from tomd.lib.pdf.types import Block, TERMINAL_PUNCTUATION, compute_bbox
import tomd.lib.pdf.cleanup as cleanup_mod
from tomd.lib.pdf.pipeline import convert_pdf

_original_join = cleanup_mod._join_cross_page


def _fixed_join_cross_page(blocks: list[Block]) -> list[Block]:
    """Join paragraphs that span page boundaries -- ONE merge per boundary.

    Prevents the chain-reaction bug where multiple blocks from page N+1
    get absorbed into a page-N block.
    """
    if len(blocks) < 2:
        return blocks

    result = [replace(blocks[0], lines=list(blocks[0].lines))]
    merged_boundary: int | None = None

    for block in blocks[1:]:
        prev = result[-1]
        prev_text = prev.text.rstrip()
        cur_text = block.text.lstrip()

        cross_page = prev.page_num != block.page_num

        if cross_page and block.page_num != merged_boundary:
            merged_boundary = None

        if (cross_page
                and merged_boundary is None
                and prev_text
                and cur_text
                and prev_text[-1] not in TERMINAL_PUNCTUATION
                and cur_text[0].islower()):
            prev.lines.extend(block.lines)
            prev.bbox = compute_bbox([ln.bbox for ln in prev.lines])
            merged_boundary = block.page_num
        else:
            result.append(replace(block, lines=list(block.lines)))

    return result


def extract_abstract(md_text: str) -> str | None:
    """Extract abstract section text from markdown."""
    lines = md_text.split("\n")
    in_abstract = False
    abstract_lines = []
    for line in lines:
        if re.match(r"^##\s+Abstract\s*$", line, re.IGNORECASE):
            in_abstract = True
            continue
        if in_abstract:
            if re.match(r"^##\s+", line):
                break
            abstract_lines.append(line)
    if not abstract_lines:
        return None
    return "\n".join(abstract_lines).strip()


def convert_with_join(pdf_path: Path, join_fn):
    """Run convert_pdf with a specific join function monkey-patched in."""
    cleanup_mod._join_cross_page = join_fn
    try:
        md, prompts = convert_pdf(pdf_path)
        return md
    finally:
        cleanup_mod._join_cross_page = _original_join


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--single", type=str, default=None)
    parser.add_argument("--batch", action="store_true")
    args = parser.parse_args()

    if args.single:
        pdf = Path(args.single)
        print(f"=== Simulating on {pdf.name} ===\n")

        try:
            md_old = convert_with_join(pdf, _original_join)
            md_new = convert_with_join(pdf, _fixed_join_cross_page)
        except Exception as e:
            print(f"ERROR: {e}")
            return

        abs_old = extract_abstract(md_old)
        abs_new = extract_abstract(md_new)

        print(f"Abstract changed: {abs_old != abs_new}")
        print(f"Old length: {len(abs_old) if abs_old else 0} chars")
        print(f"New length: {len(abs_new) if abs_new else 0} chars")
        if abs_old != abs_new:
            print(f"\n--- OLD ABSTRACT ---")
            print(abs_old or "(none)")
            print(f"\n--- NEW ABSTRACT ---")
            print(abs_new or "(none)")
        else:
            print(f"\nAbstract (identical):")
            print(abs_old or "(none)")

    elif args.batch:
        data_dir = Path(__file__).parent / "data" / "paperstore"
        pdfs = sorted(data_dir.glob("*.pdf"))
        print(f"Found {len(pdfs)} PDFs in {data_dir}\n")

        changed_papers = []
        errors = []
        total = len(pdfs)

        for i, pdf in enumerate(pdfs):
            pid = pdf.stem
            sys.stdout.write(f"\r[{i+1}/{total}] {pid}...                    ")
            sys.stdout.flush()

            try:
                md_old = convert_with_join(pdf, _original_join)
                md_new = convert_with_join(pdf, _fixed_join_cross_page)
            except Exception as e:
                errors.append((pid, str(e)))
                continue

            abs_old = extract_abstract(md_old)
            abs_new = extract_abstract(md_new)

            if abs_old != abs_new:
                changed_papers.append({
                    "pid": pid,
                    "old": abs_old,
                    "new": abs_new,
                    "old_len": len(abs_old) if abs_old else 0,
                    "new_len": len(abs_new) if abs_new else 0,
                })

        print(f"\n\n{'='*72}")
        print(f"  BATCH RESULTS: {total} PDFs tested")
        print(f"{'='*72}")
        print(f"  Changed abstracts: {len(changed_papers)}")
        print(f"  Errors: {len(errors)}")

        if changed_papers:
            print(f"\n{'='*72}")
            print(f"  PAPERS WITH CHANGED ABSTRACTS")
            print(f"{'='*72}")
            for r in changed_papers:
                delta = r['new_len'] - r['old_len']
                direction = "LONGER" if delta > 0 else "SHORTER" if delta < 0 else "SAME LEN"
                print(f"\n  {r['pid']}: {direction} "
                      f"({r['old_len']} -> {r['new_len']}, delta={delta:+d})")
                print(f"  OLD: {(r['old'] or '(none)')[:300]}")
                print(f"  NEW: {(r['new'] or '(none)')[:300]}")

        if errors:
            print(f"\n  ERRORS ({len(errors)}):")
            for pid, err in errors[:10]:
                print(f"    {pid}: {err[:100]}")
            if len(errors) > 10:
                print(f"    ... and {len(errors) - 10} more")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
