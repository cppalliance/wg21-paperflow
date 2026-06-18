# Concurrent conversion fixtures

PDF files used by `test_concurrent_convert.py` to reproduce the PyMuPDF thread-safety bug
described in `convert-bug-concurrent-papers.md`.

## Required files

- `p4003r1.pdf` -- P4003R1, "A Unified Reflection Facility for C++". Its section 11.3.3 table
  crosses pages 56-57. The two vector images on page 57 (`fig57-1.png`, `fig57-2.png`) duplicate
  the overflowed table row and must be dropped by `_filter_vector_images_against_structural`.
  Without `_FITZ_LOCK`, concurrent execution corrupts the TABLE coordinates for page 56, and the
  filter fails to drop them.

- `p3127r1.pdf` -- P3127R1, the second paper in the concurrent pair. Its role is to share the
  thread pool with P4003R1 and trigger the MuPDF global-state corruption.

## How to add the fixtures

1. Run `paperflow download P4003R1 P3127R1` to stage both PDFs locally.
2. Check sizes: `ls -lh "$WG21_DATA_DIR/paperstore/p4003r1.pdf" "$WG21_DATA_DIR/paperstore/p3127r1.pdf"`
3. If both are within the existing fixture range (66KB-583KB), copy them here and commit.
4. If either is larger, leave this directory empty and the test will be skipped automatically.
   In that case, create a synthetic minimal PDF that exercises the cross-page table detection
   path as a separate follow-up task.
