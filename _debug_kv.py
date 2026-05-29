import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'packages' / 'tomd' / 'src'))
import logging
logging.disable(logging.CRITICAL)
from tomd.lib.pdf.extract import extract_mupdf
from tomd.lib.pdf.table import detect_tables
import fitz

DATA = Path(r'C:\Users\sabog\Desktop\cppalliance\cppalliance\data\paperstore')
pdfs = sorted(DATA.glob('*.pdf'))
print(f'Scanning {len(pdfs)} PDFs...')
total_cm = 0
for pdf_path in pdfs:
    pid = pdf_path.stem
    try:
        doc = fitz.open(str(pdf_path))
        blocks = []
        for pg in range(doc.page_count):
            blocks.extend(extract_mupdf(doc[pg], pg))
        doc.close()
        tables, _ = detect_tables(blocks)
        for sec in tables:
            if sec.table_kind == 'clean_matrix':
                total_cm += 1
                rows = sec.columns
                ncols = len(rows[0]) if rows else 0
                r0 = []
                for cell in rows[0][:ncols]:
                    t = ''.join(s.text for s in cell).strip()[:15]
                    r0.append(t)
                print(f'  {pid}: pg={sec.page_num} rows={len(rows)} cols={ncols} strat={sec.table_strategy} hdr={r0}')
    except Exception as e:
        print(f'  {pid}: ERROR {e}')
print(f'\nTotal CLEAN_MATRIX tables: {total_cm}')
