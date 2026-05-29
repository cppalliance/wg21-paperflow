"""Detailed markdown inspection for p2034r6 Tony Tables."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

md = Path("data/paperstore/p2034r6.md").read_text(encoding="utf-8")
lines = md.split("\n")

# Find code blocks that are Tony Tables (Before/After pattern)
print("=== p2034r6: Tony Table rendering ===\n")
in_code = False
code_start = -1
for i, line in enumerate(lines):
    if "Before" in line and "After" in line and i > 10:
        print(f"Line {i+1}: {line[:100]}")
        # Show context around it
        start = max(0, i-2)
        end = min(len(lines), i+15)
        for j in range(start, end):
            marker = ">>>" if j == i else "   "
            print(f"  {marker} {j+1}: {lines[j][:100]}")
        print()
        break

# Show the first code_blocks-rendered table
found = 0
for i, line in enumerate(lines):
    if line.strip().startswith("```") and i > 50:
        # Check if this is a Tony Table code block
        end = -1
        for j in range(i+1, min(i+30, len(lines))):
            if lines[j].strip().startswith("```"):
                end = j
                break
        if end > 0:
            block = "\n".join(lines[i:end+1])
            if "|" in block and ("Before" in block or "After" in block or "move_only" in block.lower()):
                found += 1
                print(f"--- Tony Table Code Block #{found} (lines {i+1}-{end+1}) ---")
                for j in range(i, end+1):
                    print(f"  {lines[j][:120]}")
                print()
                if found >= 2:
                    break
