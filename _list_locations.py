"""List all table locations per paper for manual review."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

data = Path("data/paperstore")

papers = {
    "p2034r6": "Tony Tables (CODE_COMPARISON -> code_blocks)",
    "p3977r0": "FALSE_POSITIVE + PROSE_TABLE",
    "p4014r0": "FALSE_POSITIVE + Pipe Escape",
    "p3856r8": "PROSE_TABLE",
    "p3978r3": "CLEAN_MATRIX",
    "p3844r4": "Straw Poll (CLEAN_MATRIX)",
    "p0876r22": "Wording Index (CLEAN_MATRIX)",
    "p3596r1": "Standards Draft (129 Tables)",
    "p4016r0": "Mixed (22 Tables, inkl. PROSE)",
}

for paper, desc in papers.items():
    md_path = data / f"{paper}.md"
    if not md_path.exists():
        print(f"{paper} | {desc} | FILE NOT FOUND")
        continue
    
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    
    table_lines = []
    in_code = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if (line.strip().startswith("|") and line.strip().endswith("|")
                and i + 1 < len(lines) and "---" in lines[i+1]):
            cells = line.strip()[1:-1].split("|")
            first_cell = cells[0].strip()[:35] if cells else ""
            table_lines.append((i+1, first_cell))
    
    # Find code_blocks tables
    code_table_lines = []
    for i, line in enumerate(lines):
        if line.strip() == "```cpp" and i+1 < len(lines):
            next_l = lines[i+1]
            if ("// new vocabulary" in next_l or "// loss of" in next_l
                    or ("move_only_function" in next_l and i > 100)):
                code_table_lines.append(i+1)
    
    print(f"--- {paper} | {desc} ---")
    if code_table_lines:
        print(f"  CODE_BLOCKS (Tony Tables): Zeilen {code_table_lines}")
    for ln, cell in table_lines[:10]:
        print(f"  Zeile {ln:4}: | {cell} |...")
    if len(table_lines) > 10:
        print(f"  ... +{len(table_lines)-10} weitere Tables")
    print()
