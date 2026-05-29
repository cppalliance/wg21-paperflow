"""Analyze the scan results."""
import csv

rows = list(csv.DictReader(open("_scan_tables_inventory.csv", "r", encoding="utf-8")))
print(f"Total table rows: {len(rows)}")

print("\n=== Classification Distribution ===")
dist = {}
for r in rows:
    cls = r["classification"]
    dist[cls] = dist.get(cls, 0) + 1
for cls, count in sorted(dist.items(), key=lambda x: -x[1]):
    print(f"  {cls}: {count} ({count*100//len(rows)}%)")

print("\n=== PROSE_TABLE examples (top 10 by max_word_count) ===")
prose = [r for r in rows if r["classification"] == "PROSE_TABLE"]
prose.sort(key=lambda r: -int(r["max_word_count"]))
for r in prose[:10]:
    print(f"  {r['paper_id']} t{r['table_index']} cols={r['num_cols']} rows={r['num_rows']} max_words={r['max_word_count']} mono={r['mono_ratio']} links={r['has_links']}")

print("\n=== CODE_COMPARISON examples (all) ===")
code = [r for r in rows if r["classification"] == "CODE_COMPARISON"]
for r in code:
    print(f"  {r['paper_id']} t{r['table_index']} cols={r['num_cols']} rows={r['num_rows']} mono={r['mono_ratio']} max_words={r['max_word_count']}")

print("\n=== FALSE_POSITIVE examples (all) ===")
fp = [r for r in rows if r["classification"] == "FALSE_POSITIVE"]
for r in fp:
    print(f"  {r['paper_id']} t{r['table_index']} cols={r['num_cols']} rows={r['num_rows']} empty={r['empty_ratio']} consistent={r['col_count_consistent']}")

print("\n=== Papers with most tables ===")
paper_counts = {}
for r in rows:
    pid = r["paper_id"]
    paper_counts[pid] = paper_counts.get(pid, 0) + 1
top_papers = sorted(paper_counts.items(), key=lambda x: -x[1])[:15]
for pid, count in top_papers:
    print(f"  {pid}: {count} tables")

print("\n=== CLEAN_MATRIX signal ranges ===")
clean = [r for r in rows if r["classification"] == "CLEAN_MATRIX"]
max_words_clean = [int(r["max_word_count"]) for r in clean]
print(f"  max_word_count: min={min(max_words_clean)} max={max(max_words_clean)} median={sorted(max_words_clean)[len(max_words_clean)//2]}")
cols_clean = [int(r["num_cols"]) for r in clean]
print(f"  num_cols: min={min(cols_clean)} max={max(cols_clean)} median={sorted(cols_clean)[len(cols_clean)//2]}")
rows_clean = [int(r["num_rows"]) for r in clean]
print(f"  num_rows: min={min(rows_clean)} max={max(rows_clean)} median={sorted(rows_clean)[len(rows_clean)//2]}")
