"""Check table extraction quality for all papers referenced in the ticket."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

data = Path("data/paperstore")

# Papers from the ticket with known table issues/types
ticket_papers = [
    "p2034r6",   # Tony Tables (CODE_COMPARISON)
    "p3839r0",   # FALSE_POSITIVE (layout artefact)
    "p3977r0",   # FALSE_POSITIVE
    "p4014r0",   # FALSE_POSITIVE + pipe escape
    "p3688r6",   # pipe escape
    "p3985r0",   # pipe escape
    "p4006r0",   # pipe escape
    "p0533r9",   # code-declaration tables (must stay pipe)
    "p0957r8",   # code-declaration tables (must stay pipe)
    "p3856r8",   # prose table
    "p3978r3",   # clean matrix
    "p3844r4",   # straw poll
    "p0876r22",  # wording index
    "p3596r1",   # many tables (standards draft)
    "p4016r0",   # space-aligned (deferred, no tables detected)
]

for paper in ticket_papers:
    md_path = data / f"{paper}.md"
    if not md_path.exists():
        print(f"  {paper}: FILE NOT FOUND")
        continue
    
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    
    # Count tables and code blocks
    in_code = False
    tables = 0
    code_blocks = 0
    pipe_escapes = 0
    
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            if not in_code:
                code_blocks += 1
            continue
        if in_code:
            continue
        if (line.strip().startswith("|") and line.strip().endswith("|")
                and i + 1 < len(lines) and "---" in lines[i+1]):
            tables += 1
        if "\\|" in line:
            pipe_escapes += 1
    
    print(f"=== {paper} ===")
    print(f"  Tables: {tables}, Code blocks: {code_blocks}, Pipe escapes: {pipe_escapes}")
    
    # Show first table (first 4 lines)
    in_code = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if (line.strip().startswith("|") and line.strip().endswith("|")
                and i + 1 < len(lines) and "---" in lines[i+1]):
            print(f"  First table (line {i+1}):")
            for j in range(i, min(i+4, len(lines))):
                print(f"    {lines[j][:100]}")
            break
    print()
