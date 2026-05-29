"""Comprehensive quality check on all regenerated ticket papers."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

data = Path("data/paperstore")

papers = {
    "p2034r6": "Tony Tables (code_blocks)",
    "p3977r0": "FALSE_POSITIVE + prose",
    "p4014r0": "FALSE_POSITIVE + pipe escape",
    "p3856r8": "prose table",
    "p3978r3": "clean matrix",
    "p3844r4": "straw poll",
    "p0876r22": "wording index",
    "p3596r1": "many tables (standards draft)",
    "p4016r0": "space-aligned (23 tables)",
}

for paper, desc in papers.items():
    md_path = data / f"{paper}.md"
    if not md_path.exists():
        print(f"=== {paper} ({desc}): FILE NOT FOUND ===\n")
        continue
    
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    
    # Count tables, code blocks, pipe escapes, false-positive skips
    pipe_tables = 0
    code_blocks = 0
    pipe_escapes = 0
    in_code = False
    
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                code_blocks += 1
            else:
                in_code = False
            continue
        if in_code:
            continue
        if (line.strip().startswith("|") and line.strip().endswith("|")
                and i + 1 < len(lines) and "---" in lines[i+1]):
            pipe_tables += 1
        if "\\|" in line:
            pipe_escapes += 1
    
    print(f"=== {paper} ({desc}) ===")
    print(f"  Pipe tables: {pipe_tables}, Code blocks: {code_blocks}, "
          f"Pipe escapes: {pipe_escapes}")
    
    # Show first 2 pipe tables (first 3 lines each)
    shown = 0
    in_code = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if (line.strip().startswith("|") and line.strip().endswith("|")
                and i + 1 < len(lines) and "---" in lines[i+1]):
            shown += 1
            if shown <= 2:
                print(f"  Table {shown} (line {i+1}):")
                for j in range(i, min(i+3, len(lines))):
                    print(f"    {lines[j][:100]}")
            if shown >= 2:
                break
    
    # Check for escaped pipes in context
    if pipe_escapes:
        shown_esc = 0
        in_code = False
        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if "\\|" in line:
                shown_esc += 1
                if shown_esc <= 2:
                    print(f"  Pipe escape (line {i+1}): ...{line[max(0,line.index(chr(92)+'|')-20):line.index(chr(92)+'|')+20]}...")
    print()
