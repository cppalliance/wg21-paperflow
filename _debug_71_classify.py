import sys, pathlib
sys.path.insert(0, str(pathlib.Path('.').resolve() / 'packages' / 'tomd' / 'src'))
from tomd.lib.pdf.pipeline import _run_pipeline

pdf_path = pathlib.Path(r'data\paperstore\p4088r0.pdf')
result = _run_pipeline(pdf_path)
sections = result.sections

for i, s in enumerate(sections):
    if s.kind.value != 'table':
        continue
    cols = getattr(s, 'columns', None)
    num_rows = len(cols) if isinstance(cols, list) else 0
    num_cols_per_row = 0
    if num_rows > 0 and isinstance(cols[0], list):
        num_cols_per_row = len(cols[0])
    print(f'=== Section [{i}] page={s.page_num} ===')
    print(f'  table_kind: {s.table_kind}')
    print(f'  table_strategy: {s.table_strategy}')
    print(f'  num_rows: {num_rows}, num_cols_per_row: {num_cols_per_row}')
    print(f'  text (first 300 chars): {s.text[:300]}')
    print()
