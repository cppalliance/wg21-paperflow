"""Table detection from MuPDF block/line structure.

Three detection passes:

Pass 1 (inline-column tables):
  Signal 1 (block structure): a block is columnar when it has 2+ lines whose
    x-starts have gaps > _COLUMN_GAP_THRESHOLD. Consecutive matching-column
    blocks form a table run.
  Signal 2 (geometric column profile): x positions that co-occur with other
    x positions in the same y-band across 2+ rows are confirmed table columns.
    Body text is always alone in its y-band and never qualifies.

  Orphan absorption: single-line blocks whose x0 matches a confirmed column are
  "orphans" - the first physical line of a wrapped table cell. They are absorbed
  into the table run when the block following them is a confirmed table row
  (one-block lookahead). Absorbed orphans are merged into the next row's first
  cell so multi-line cells produce a single cell string.

  Known gap: absorption is same-page only. A wrapped cell whose continuation
  line is the first block on the next page is not absorbed - the table stops
  at the last same-page row and the orphan appears in an uncertain region.

Pass 2 (side-by-side block tables):
  Detects tables where each cell is a separate MuPDF block placed beside
  other blocks at a different x-position (e.g. Tony Tables with multi-line
  code cells). A columnar header block signals a table start; subsequent
  blocks that align with confirmed column x-positions and overlap vertically
  form table rows. A new row begins when a new leftmost-column block appears.

Pass 3 (geometric column grouping):
  Catches tables missed by Passes 1-2 where MuPDF distributes columns across
  separate single-column blocks (e.g. schedule tables with dates in left-column
  blocks and descriptions in right-column blocks, or multi-column comparison
  tables where each cell is its own block).  Uses the geometric column profile
  from _find_column_xs to identify confirmed column positions, then groups
  remaining blocks into rows by y-overlap. Requires 2+ columns and 2+ rows.
"""

import logging
import re
from collections import Counter, defaultdict
from enum import Enum

from .types import Block, Span, Section, SectionKind, Confidence

_log = logging.getLogger(__name__)


_COLUMN_GAP_THRESHOLD = 50.0
_MIN_TABLE_ROWS = 2
_COLUMN_X_TOLERANCE = 10.0
_TABLE_Y_OVERLAP_MARGIN = 5.0

_COLUMN_X_BUCKET = 5.0    # bucket size for x-position clustering
_Y_BAND_HEIGHT   = 15.0   # bucket size for y-position clustering
_MIN_SHARED_YBANDS = 2    # x must co-occur with other columns in 2+ y-bands

# Partial-row absorption: a columnar block with fewer columns than the
# table header may be a row whose rightmost columns were split into
# separate blocks by MuPDF.  Accept it when all its x-positions are a
# subset of the table's reference columns and the y-gap is small.
_PARTIAL_ROW_MAX_Y_GAP = 25.0

# Side-by-side table constants
_SBS_MAX_SCAN_GAP = 30.0  # max y-gap before stopping body scan

# Guard: bare section number on line 0 of a 2-line block.
# Prevents misclassifying heading blocks (large bold number + right-aligned
# title) as tables. Kretz-style LaTeX papers (P3948, P3844, P4012) produce
# blocks where the section number sits at x=73 and the ALL-CAPS title at
# x=440+, a gap of ~370pt that far exceeds _COLUMN_GAP_THRESHOLD.
_BARE_HEADING_NUM_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*|[A-Z]+|[IVXLCDM]+)\.?\s*$"
)
_HEADING_NUM_MAX_WORDS = 8


# ---------------------------------------------------------------------------
# Table classification (integrated from table_analyzer.py)
# Thresholds corpus-validated against 768 tables from 124 WG21 PDFs.
# ---------------------------------------------------------------------------

class TableKind(Enum):
    """What kind of table this section represents."""
    CLEAN_MATRIX = "clean_matrix"
    PROSE_TABLE = "prose_table"
    CODE_COMPARISON = "code_comparison"
    FALSE_POSITIVE = "false_positive"


class TableStrategy(Enum):
    """How to render this table in markdown."""
    PIPE_TABLE = "pipe_table"
    CODE_BLOCKS = "code_blocks"
    HTML_TABLE = "html_table"
    SKIP = "skip"


_STRATEGY_MAP = {
    TableKind.CLEAN_MATRIX: TableStrategy.PIPE_TABLE,
    TableKind.PROSE_TABLE: TableStrategy.PIPE_TABLE,
    TableKind.CODE_COMPARISON: TableStrategy.HTML_TABLE,
    TableKind.FALSE_POSITIVE: TableStrategy.SKIP,
}

_EMPTY_RATIO_THRESHOLD = 0.50
_MONO_RATIO_THRESHOLD = 0.70
_PROSE_WORD_THRESHOLD = 15


def _render_table_text(rows: list[list[list]]) -> str:
    """Render table rows (list of cells, each cell a list of Spans) to pipe-delimited text."""
    return "\n".join(
        " | ".join(
            "".join(s.text for s in cell).strip()
            for cell in row
        )
        for row in rows
    )


def _find_column_xs(blocks: list[Block]) -> frozenset[float]:
    """Return x-start positions that are genuine table columns.

    Uses the shared-y-band approach: an x position qualifies only when it
    co-occurs in the same y-band with at least one other distinct x position,
    across at least _MIN_SHARED_YBANDS such y-bands. Body text at the left
    margin is alone in every y-band and therefore never qualifies.

    Y-bands are scoped per page so that two lines on different pages at the
    same absolute y coordinate are not treated as sharing a row.
    """
    yband_to_xs: dict[tuple[int, int], set[int]] = defaultdict(set)
    for block in blocks:
        for line in block.lines:
            if not line.spans or not line.text.strip():
                continue
            x_key = round(line.bbox[0] / _COLUMN_X_BUCKET)
            y_key = round(((line.bbox[1] + line.bbox[3]) / 2.0) / _Y_BAND_HEIGHT)
            yband_to_xs[(block.page_num, y_key)].add(x_key)

    shared_counts: Counter[int] = Counter()
    for xs in yband_to_xs.values():
        if len(xs) >= 2:
            for x_key in xs:
                shared_counts[x_key] += 1

    return frozenset(
        x_key * _COLUMN_X_BUCKET
        for x_key, count in shared_counts.items()
        if count >= _MIN_SHARED_YBANDS
    )


def _is_column_aligned_orphan(block: Block, column_xs: frozenset[float]) -> bool:
    """True if block is a single-line block whose x0 aligns with a known column.

    Only single-line blocks qualify. Multi-line non-columnar blocks are genuine
    prose or captions and must not be absorbed into a table run.
    """
    if len(block.lines) != 1 or not block.lines[0].spans:
        return False
    x0 = block.lines[0].bbox[0]
    return any(abs(x0 - cx) <= _COLUMN_X_BUCKET for cx in column_xs)


def _is_partial_row(block: Block, ref_cols: list[float],
                    prev_bottom: float, same_page: bool) -> bool:
    """True if block is a columnar row with fewer columns than ref_cols.

    Matches when ALL of the block's column x-positions align with a subset
    of the reference columns, the block is on the same page, and the
    vertical gap is within _PARTIAL_ROW_MAX_Y_GAP.
    """
    cols = _block_column_positions(block)
    if cols is None or len(cols) >= len(ref_cols):
        return False
    if not same_page:
        return False
    y_gap = block.bbox[1] - prev_bottom
    if y_gap > _PARTIAL_ROW_MAX_Y_GAP or y_gap < 0:
        return False
    for x in cols:
        if not any(abs(x - rx) < _COLUMN_X_TOLERANCE for rx in ref_cols):
            return False
    return True


def _is_trailing_continuation(block: Block, ref_cols: list[float],
                               prev_bottom: float, same_page: bool) -> bool:
    """True if block is a single-line block continuing a non-first column.

    Trailing continuations appear after the last full row when a cell's
    text wraps across multiple PDF lines delivered as separate blocks.
    The non-first-column guard distinguishes them from new paragraphs
    which start at the left margin (column 0).
    """
    if len(block.lines) != 1 or not block.lines[0].spans:
        return False
    if not same_page:
        return False
    y_gap = block.bbox[1] - prev_bottom
    if y_gap > _PARTIAL_ROW_MAX_Y_GAP or y_gap < 0:
        return False
    x0 = block.lines[0].bbox[0]
    return any(abs(x0 - ref_cols[ci]) <= _COLUMN_X_TOLERANCE
               for ci in range(1, len(ref_cols)))


def _block_column_positions(block: Block) -> list[float] | None:
    """Return the x-start positions of columns in a block, or None.

    A block is columnar if it has 2+ lines where every line after
    the first starts significantly to the right of the first line's
    x-start position.
    """
    if len(block.lines) < 2:
        return None

    # Guard: 2-line blocks where line 0 is a bold bare section number in a
    # heading-sized font are section headings, not table rows. The title text
    # on line 1 is right-aligned or centered, creating a large x-gap that
    # would otherwise trigger columnar detection.
    if len(block.lines) == 2:
        line0 = block.lines[0]
        line1 = block.lines[1]
        if (line0.is_bold
                and _BARE_HEADING_NUM_RE.match(line0.text.strip())
                and line0.font_size > line1.font_size
                and len(line1.text.split()) <= _HEADING_NUM_MAX_WORDS):
            return None

    x_starts = []
    for line in block.lines:
        if not line.spans:
            return None
        x_starts.append(line.bbox[0])

    for i in range(1, len(x_starts)):
        if x_starts[i] - x_starts[0] < _COLUMN_GAP_THRESHOLD:
            return None

    return x_starts


def _columns_match(cols_a: list[float], cols_b: list[float]) -> bool:
    """Check if two column position lists represent the same table structure."""
    if len(cols_a) != len(cols_b):
        return False
    return all(abs(a - b) < _COLUMN_X_TOLERANCE for a, b in zip(cols_a, cols_b))


# Max y-gap between consecutive columnar blocks to consider them part of the
# same table when they share a column count but differ in x-positions (e.g.
# centered header row + left-aligned data rows).
_RELAXED_MATCH_MAX_Y_GAP = 40.0


def _columns_count_match(cols_a: list[float], cols_b: list[float],
                         block_a_bottom: float, block_b_top: float,
                         same_page: bool) -> bool:
    """Relaxed match: same column count, same page, close y-proximity.

    Handles PDF tables where header cells are centered differently from
    data cells.  The column count is identical but x-positions differ by
    more than _COLUMN_X_TOLERANCE.
    """
    if not same_page:
        return False
    if len(cols_a) != len(cols_b):
        return False
    if len(cols_a) < 2:
        return False
    if block_b_top - block_a_bottom > _RELAXED_MATCH_MAX_Y_GAP:
        return False
    return True


def _cluster_x_positions(x_vals: list[float],
                         gap: float = _COLUMN_GAP_THRESHOLD) -> list[float]:
    """Cluster nearby x values, return sorted representative per cluster."""
    if not x_vals:
        return []
    xs = sorted(set(round(x, 1) for x in x_vals))
    clusters: list[list[float]] = [[xs[0]]]
    for x in xs[1:]:
        if x - clusters[-1][-1] < gap:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [min(c) for c in clusters]


def _nearest_column(x: float, col_xs: list[float]) -> int:
    """Return index of nearest column in col_xs for position x."""
    return min(range(len(col_xs)), key=lambda ci: abs(x - col_xs[ci]))


def _detect_side_by_side_tables(
    blocks: list[Block],
) -> tuple[list[Section], set[int]]:
    """Detect tables where each cell is a separate side-by-side block.

    Returns (table_sections, used_block_indices).
    """
    table_sections: list[Section] = []
    used: set[int] = set()
    i = 0

    while i < len(blocks):
        cols = _block_column_positions(blocks[i])
        if cols is None or len(cols) < 2:
            i += 1
            continue

        header = blocks[i]
        page = header.page_num
        h_bottom = header.bbox[3]

        # Gather body candidates: same page, below header
        body_candidates: list[tuple[int, Block]] = []
        j = i + 1
        while j < len(blocks):
            b = blocks[j]
            if b.page_num != page:
                break
            if b.bbox[1] >= h_bottom - _TABLE_Y_OVERLAP_MARGIN:
                body_candidates.append((j, b))
            j += 1

        if not body_candidates:
            i += 1
            continue

        # Determine column structure from body block x-positions
        body_xs = [b.bbox[0] for _, b in body_candidates]
        col_xs = _cluster_x_positions(body_xs)

        if len(col_xs) < 2:
            i += 1
            continue

        # Guard: body suggests more columns than the header declares.
        # A non-table block (caption, label) sitting at a third x-position
        # inflates col_xs. Reject so Pass 4 (MuPDF native) handles it.
        if len(col_xs) > len(cols):
            i += 1
            continue

        # Group candidates into rows.
        # A new row starts when a block in column 0 (leftmost) appears
        # and column 0 was already populated in the current row.
        rows: list[list[tuple[int, Block]]] = []
        current_row: list[tuple[int, Block]] = []
        has_col0 = False
        last_bottom = h_bottom

        for idx, blk in body_candidates:
            col = _nearest_column(blk.bbox[0], col_xs)
            if blk.bbox[1] - last_bottom > _SBS_MAX_SCAN_GAP:
                if current_row:
                    rows.append(current_row)
                break
            if col == 0:
                if has_col0:
                    rows.append(current_row)
                    current_row = [(idx, blk)]
                    has_col0 = True
                else:
                    current_row.append((idx, blk))
                    has_col0 = True
            else:
                current_row.append((idx, blk))
            last_bottom = max(last_bottom, blk.bbox[3])

        if current_row and current_row not in rows:
            rows.append(current_row)

        # Validate: each row must have blocks in 2+ columns
        valid_rows: list[list[tuple[int, Block]]] = []
        for row in rows:
            row_cols = set(_nearest_column(b.bbox[0], col_xs) for _, b in row)
            if len(row_cols) >= 2:
                valid_rows.append(row)
            else:
                break

        if len(valid_rows) < _MIN_TABLE_ROWS:
            i += 1
            continue

        num_cols = len(col_xs)

        # Build header row from the columnar header block
        header_cells: list[list] = []
        for ln in header.lines[:num_cols]:
            header_cells.append(list(ln.spans))
        while len(header_cells) < num_cols:
            header_cells.append([])

        all_rows_data: list[list[list]] = [header_cells]
        all_lines = list(header.lines)

        for row in valid_rows:
            col_spans: dict[int, list] = defaultdict(list)
            for _, blk in row:
                ci = _nearest_column(blk.bbox[0], col_xs)
                for ln in blk.lines:
                    if col_spans[ci] and ln.spans:
                        col_spans[ci].append(Span(text="\n"))
                    col_spans[ci].extend(ln.spans)
                    all_lines.append(ln)
            table_row = [col_spans.get(ci, []) for ci in range(num_cols)]
            all_rows_data.append(table_row)

        kind_val, strategy_val, all_rows_data = _classify_and_annotate(
            all_rows_data)
        text = _render_table_text(all_rows_data)

        table_sections.append(Section(
            kind=SectionKind.TABLE,
            text=text,
            confidence=Confidence.HIGH,
            lines=all_lines,
            page_num=page,
            columns=all_rows_data,
            table_kind=kind_val,
            table_strategy=strategy_val,
        ))
        _log.debug("Side-by-side table: %d rows x %d cols on page %d",
                    len(all_rows_data), num_cols, page)

        used.add(i)
        for row in valid_rows:
            for idx, _ in row:
                used.add(idx)

        i = j

    return table_sections, used


_MUPDF_TABLE_MIN_BBOX_SIZE = 50.0  # minimum width AND height for a real table


_LABEL_MAX_WORDS = 3  # column-0 cells with more words are not labels


def _maybe_transpose_label_table(
    rows: list[list[list]],
) -> list[list[list]]:
    """Transpose a table whose first column contains short row labels.

    Detects tables where column 0 has short non-monospace labels
    (e.g. "Before", "After") at certain rows, with remaining rows
    holding data or continuation content. Transposes so the labels
    become column headers, and all content from each label group
    merges into one data cell per label.

    Handles both simple (2-row) and multi-row (4+ row) tables
    uniformly. Continuation rows between labels have their content
    from all columns merged into the preceding label's data cell.
    """
    if len(rows) < 2 or len(rows[0]) < 2:
        return rows

    num_cols = len(rows[0])
    if num_cols != 2:
        return rows

    # Scan column 0 for short non-monospace labels.
    labels: list[str] = []
    label_indices: list[int] = []
    for ri, row in enumerate(rows):
        cell0_text = "".join(s.text for s in row[0]).strip()
        if not cell0_text:
            continue
        words = cell0_text.split()
        is_mono = any(s.monospace for s in row[0] if s.text.strip())
        if len(words) <= _LABEL_MAX_WORDS and not is_mono:
            labels.append(cell0_text)
            label_indices.append(ri)

    if len(labels) < 2:
        return rows

    # Build transposed table: labels become column headers.
    new_num_cols = len(labels)
    header_row: list[list] = [list(rows[ri][0]) for ri in label_indices]

    # For each label, collect ALL content from its group rows
    # (label row through next label - 1) across all columns,
    # excluding the label text in column 0 of the label row.
    data_cells: list[list] = [[] for _ in range(new_num_cols)]
    for li, start_ri in enumerate(label_indices):
        end_ri = (label_indices[li + 1]
                  if li + 1 < len(label_indices) else len(rows))
        for ri in range(start_ri, end_ri):
            for ci in range(num_cols):
                # Skip the label cell itself (col 0 of the label row).
                if ri == start_ri and ci == 0:
                    continue
                cell_spans = rows[ri][ci]
                if cell_spans:
                    if data_cells[li]:
                        data_cells[li].append(Span(text="\n"))
                    data_cells[li].extend(cell_spans)

    return [header_row, data_cells]


def _detect_mupdf_native_tables(
    blocks: list[Block],
    page_mupdf_tables: dict[int, list[dict]],
) -> tuple[list[Section], set[int]]:
    """Detect tables using MuPDF's native find_tables() results.

    Maps pre-collected find_tables() data (cell bboxes) back to the
    existing Block/Line/Span objects so that classification and
    rendering can use monospace and font information.

    Returns (table_sections, used_block_indices).
    """
    table_sections: list[Section] = []
    used: set[int] = set()

    if not page_mupdf_tables:
        return table_sections, used

    for page_num in sorted(page_mupdf_tables):
        for tbl_info in page_mupdf_tables[page_num]:
            bbox = tbl_info["bbox"]
            row_count = tbl_info["row_count"]
            col_count = tbl_info["col_count"]
            cells = tbl_info["cells"]

            if row_count < 2 or col_count < 1:
                continue
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w < _MUPDF_TABLE_MIN_BBOX_SIZE or h < _MUPDF_TABLE_MIN_BBOX_SIZE:
                continue

            # Build cell grid by clustering cell bboxes by y-position
            # (rows) and x-position (columns). find_tables() may return
            # cells in column-major order for some table layouts, so
            # relying on ri*col_count+ci is unreliable. Instead, group
            # cells spatially.
            valid_cells = [c for c in cells if c is not None]
            if len(valid_cells) < 2:
                continue

            # Cluster y-midpoints into rows.
            y_mids = sorted(set(
                round((c[1] + c[3]) / 2.0, 1) for c in valid_cells))
            y_clusters: list[float] = []
            for ym in y_mids:
                if not y_clusters or abs(ym - y_clusters[-1]) > 10.0:
                    y_clusters.append(ym)
                else:
                    y_clusters[-1] = (y_clusters[-1] + ym) / 2.0

            # Cluster x-midpoints into columns.
            x_mids = sorted(set(
                round((c[0] + c[2]) / 2.0, 1) for c in valid_cells))
            x_clusters: list[float] = []
            for xm in x_mids:
                if not x_clusters or abs(xm - x_clusters[-1]) > 10.0:
                    x_clusters.append(xm)
                else:
                    x_clusters[-1] = (x_clusters[-1] + xm) / 2.0

            actual_rows = len(y_clusters)
            actual_cols = len(x_clusters)
            if actual_rows < 2 or actual_cols < 1:
                continue

            # Assign each cell to (row_idx, col_idx) by closest cluster.
            cell_grid: list[list[tuple[float, float, float, float] | None]] = [
                [None] * actual_cols for _ in range(actual_rows)
            ]
            for c in valid_cells:
                cy = (c[1] + c[3]) / 2.0
                cx = (c[0] + c[2]) / 2.0
                ri = min(range(actual_rows),
                         key=lambda r: abs(cy - y_clusters[r]))
                ci = min(range(actual_cols),
                         key=lambda c_: abs(cx - x_clusters[c_]))
                cell_grid[ri][ci] = c

            row_count = actual_rows
            col_count = actual_cols

            # Collect blocks that fall within the table bbox (with margin).
            margin = 5.0
            table_block_indices: list[int] = []
            for idx, blk in enumerate(blocks):
                if idx in used:
                    continue
                if blk.page_num != page_num:
                    continue
                bmid_y = (blk.bbox[1] + blk.bbox[3]) / 2.0
                bmid_x = (blk.bbox[0] + blk.bbox[2]) / 2.0
                if (bbox[0] - margin <= bmid_x <= bbox[2] + margin
                        and bbox[1] - margin <= bmid_y <= bbox[3] + margin):
                    table_block_indices.append(idx)

            if not table_block_indices:
                continue

            # Map each line from collected blocks into the cell grid.
            all_rows_data: list[list[list]] = [
                [[] for _ in range(col_count)] for _ in range(row_count)
            ]
            all_lines = []

            for idx in table_block_indices:
                blk = blocks[idx]
                for ln in blk.lines:
                    lmid_x = (ln.bbox[0] + ln.bbox[2]) / 2.0
                    lmid_y = (ln.bbox[1] + ln.bbox[3]) / 2.0

                    best_r, best_c = -1, -1
                    best_score = float("inf")
                    for ri in range(row_count):
                        for ci in range(col_count):
                            cb = cell_grid[ri][ci]
                            if cb is None:
                                continue
                            if (cb[0] - margin <= lmid_x <= cb[2] + margin
                                    and cb[1] - margin <= lmid_y <= cb[3] + margin):
                                cw = max(cb[2] - cb[0], 1.0)
                                ch = max(cb[3] - cb[1], 1.0)
                                nx = abs(lmid_x - (cb[0] + cb[2]) / 2.0) / cw
                                ny = abs(lmid_y - (cb[1] + cb[3]) / 2.0) / ch
                                score = nx + ny
                                if score < best_score:
                                    best_score = score
                                    best_r, best_c = ri, ci

                    if best_r >= 0:
                        cell = all_rows_data[best_r][best_c]
                        if cell and ln.spans:
                            cell.append(Span(text="\n"))
                        cell.extend(ln.spans)
                        all_lines.append(ln)

            # Cross-page continuation: when the table bbox extends
            # close to the page bottom, absorb code blocks from the
            # top of the next page that fall within the table's
            # x-range. Only monospace blocks qualify; stop at the
            # first non-monospace block (heading, caption, body text).
            _PAGE_BOTTOM_THRESH = 650.0
            next_page = page_num + 1
            if bbox[3] > _PAGE_BOTTOM_THRESH and col_count >= 2:
                cont_row: list[list] = [[] for _ in range(col_count)]
                table_mid = (bbox[0] + bbox[2]) / 2.0
                for idx, blk in enumerate(blocks):
                    if idx in used:
                        continue
                    if blk.page_num != next_page:
                        continue
                    if blk.bbox[1] > 200.0:
                        break
                    if not all(ln.is_monospace for ln in blk.lines):
                        break
                    bmid_x = (blk.bbox[0] + blk.bbox[2]) / 2.0
                    if bbox[0] - margin <= bmid_x <= bbox[2] + margin:
                        for ln in blk.lines:
                            lmid_x = (ln.bbox[0] + ln.bbox[2]) / 2.0
                            best_c = (0 if lmid_x < table_mid
                                      else col_count - 1)
                            cell = cont_row[best_c]
                            if cell and ln.spans:
                                cell.append(Span(text="\n"))
                            cell.extend(ln.spans)
                            all_lines.append(ln)
                        table_block_indices.append(idx)
                        used.add(idx)
                if any(cell for cell in cont_row):
                    all_rows_data.append(cont_row)

            # Drop rows that are completely empty.
            non_empty_rows = [
                r for r in all_rows_data
                if any(cell for cell in r)
            ]
            if len(non_empty_rows) < 2:
                continue

            # Transpose comparison tables: when column 0 contains only
            # short labels (e.g. "Before", "After") and column 1+ has
            # longer content, restructure so the labels become column
            # headers and corresponding data fills the columns below.
            non_empty_rows = _maybe_transpose_label_table(non_empty_rows)

            used.update(table_block_indices)

            text = _render_table_text(non_empty_rows)

            # Exclude a short header row from classification signals
            # so non-monospace labels don't dilute mono_ratio.
            classify_rows = non_empty_rows
            if (len(non_empty_rows) > 1
                    and all(len(cell) <= 1 for cell in non_empty_rows[0])
                    and sum(len("".join(s.text for s in cell).split())
                            for cell in non_empty_rows[0]) <= col_count):
                classify_rows = non_empty_rows[1:]

            kind_val, strategy_val, classify_rows = (
                _classify_and_annotate(classify_rows))
            non_empty_rows = classify_rows

            table_sections.append(Section(
                kind=SectionKind.TABLE,
                text=text,
                confidence=Confidence.HIGH,
                lines=all_lines,
                page_num=page_num,
                columns=non_empty_rows,
                table_kind=kind_val,
                table_strategy=strategy_val,
            ))
            _log.debug(
                "MuPDF native table: %d rows x %d cols on page %d (%s)",
                len(non_empty_rows), col_count, page_num, kind_val,
            )

    return table_sections, used


_HORIZONTAL_ROW_Y_TOLERANCE = 3.0
_HORIZONTAL_ROW_MIN_CELLS = 3


def _block_horizontal_row(block: Block) -> list[float] | None:
    """Detect a block whose lines sit side-by-side at the same y-level.

    Returns x-start positions when the block has 3+ lines sharing
    the same y-band (within _HORIZONTAL_ROW_Y_TOLERANCE). This
    catches narrow poll/vote tables where column gaps are too small
    for _block_column_positions.
    """
    if len(block.lines) < _HORIZONTAL_ROW_MIN_CELLS:
        return None
    y_centers = [(ln.bbox[1] + ln.bbox[3]) / 2 for ln in block.lines]
    if max(y_centers) - min(y_centers) > _HORIZONTAL_ROW_Y_TOLERANCE:
        return None
    return [ln.bbox[0] for ln in block.lines]


def _detect_horizontal_row_tables(
    blocks: list[Block],
) -> tuple[list[Section], set[int]]:
    """Detect tables formed by consecutive horizontal-row blocks.

    Two or more adjacent blocks on the same page, each with 3+ lines
    at identical y-level and matching cell count, form a table.
    """
    table_sections: list[Section] = []
    used: set[int] = set()
    i = 0

    while i < len(blocks):
        cols = _block_horizontal_row(blocks[i])
        if cols is None:
            i += 1
            continue

        run = [i]
        ncols = len(cols)
        j = i + 1
        while j < len(blocks):
            nxt_cols = _block_horizontal_row(blocks[j])
            if (nxt_cols is not None
                    and len(nxt_cols) == ncols
                    and blocks[j].page_num == blocks[i].page_num):
                run.append(j)
                j += 1
            else:
                break

        if len(run) >= _MIN_TABLE_ROWS:
            rows: list[list[list]] = []
            all_lines = []
            for idx in run:
                blk = blocks[idx]
                row = []
                for ln in blk.lines[:ncols]:
                    row.append(list(ln.spans))
                    all_lines.append(ln)
                while len(row) < ncols:
                    row.append([])
                rows.append(row)

            kind_val, strategy_val, rows = _classify_and_annotate(rows)
            text = _render_table_text(rows)

            table_sections.append(Section(
                kind=SectionKind.TABLE,
                text=text,
                confidence=Confidence.HIGH,
                lines=all_lines,
                page_num=blocks[run[0]].page_num,
                columns=rows,
                table_kind=kind_val,
                table_strategy=strategy_val,
            ))
            _log.debug(
                "Horizontal-row table: %d rows x %d cols on page %d",
                len(rows), ncols, blocks[run[0]].page_num,
            )
            used.update(run)
            i = j
        else:
            i += 1

    return table_sections, used


# ---------------------------------------------------------------------------
# Classification helpers (integrated from table_analyzer.py)
# ---------------------------------------------------------------------------

def _compute_table_signals(rows: list[list[list]]) -> dict:
    """Compute classification signals from table rows (list of cell-span-lists)."""
    if not rows:
        return {"empty": True}

    total_cells = 0
    empty_cells = 0
    monospace_cells = 0
    max_word_count = 0
    col_counts = []
    total_cell_length = 0
    total_spans = 0

    for row in rows:
        col_counts.append(len(row))
        for cell_spans in row:
            total_cells += 1
            total_spans += len(cell_spans)
            cell_text = "".join(s.text for s in cell_spans).strip()
            if not cell_text:
                empty_cells += 1
                continue

            total_cell_length += len(cell_text)
            words = cell_text.split()
            if len(words) > max_word_count:
                max_word_count = len(words)

            text_spans = [s for s in cell_spans if s.text.strip()]
            if text_spans and all(s.monospace for s in text_spans):
                monospace_cells += 1

    non_empty = total_cells - empty_cells
    num_cols = max(col_counts) if col_counts else 0
    return {
        "empty": False,
        "empty_ratio": empty_cells / total_cells if total_cells > 0 else 0,
        "mono_ratio": monospace_cells / non_empty if non_empty > 0 else 0,
        "max_word_count": max_word_count,
        "col_count_consistent": len(set(col_counts)) <= 2,
        "num_cols": num_cols,
        "num_rows": len(rows),
        "avg_cell_length": total_cell_length / non_empty if non_empty > 0 else 0,
        "avg_spans_per_cell": total_spans / total_cells if total_cells > 0 else 0,
    }


def _classify_table(signals: dict) -> TableKind:
    """Classify a table based on its computed signals."""
    if signals.get("empty"):
        return TableKind.FALSE_POSITIVE

    if signals["empty_ratio"] > _EMPTY_RATIO_THRESHOLD:
        return TableKind.FALSE_POSITIVE

    if not signals["col_count_consistent"]:
        return TableKind.FALSE_POSITIVE

    # Tony Tables: few rows, many spans per cell (multi-line code packed
    # into each cell by MuPDF).
    if (signals["mono_ratio"] >= _MONO_RATIO_THRESHOLD
            and signals.get("num_cols", 0) <= 3
            and signals.get("num_rows", 0) <= 5
            and signals.get("avg_spans_per_cell", 0) > 10):
        return TableKind.CODE_COMPARISON

    # Per-line code tables: many rows where each cell is a single code
    # line (e.g. side-by-side struct definitions).  Distinguished from
    # code-declaration tables by high mono_ratio combined with very low
    # avg_spans_per_cell (each cell = one code token/line, not a
    # labelled signature with mixed fonts).
    if (signals["mono_ratio"] >= 0.85
            and signals.get("num_cols", 0) <= 3
            and signals.get("avg_spans_per_cell", 0) <= 3
            and signals.get("num_rows", 0) >= 4):
        return TableKind.CODE_COMPARISON

    if signals["max_word_count"] > _PROSE_WORD_THRESHOLD:
        return TableKind.PROSE_TABLE

    return TableKind.CLEAN_MATRIX


def _merge_code_rows(rows: list[list[list]]) -> list[list[list]]:
    """Merge consecutive per-line code rows into multi-line cells.

    When Pass 2 detects a side-by-side code table, MuPDF may deliver
    each code line as a separate block, producing many single-line rows.
    This merges them into one data row with newline-joined cells so the
    HTML renderer produces proper ``<pre>`` blocks.

    Only merges rows where every non-empty cell is monospace and
    contains no existing newlines (already multi-line cells stay as-is).
    The first row (header) is never merged into.
    """
    if len(rows) <= 2:
        return rows

    def _is_single_line_code_row(row: list[list]) -> bool:
        """True if every non-empty cell is monospace with no newlines."""
        for cell_spans in row:
            text = "".join(s.text for s in cell_spans).strip()
            if not text:
                continue
            text_spans = [s for s in cell_spans if s.text.strip()]
            if not text_spans or not all(s.monospace for s in text_spans):
                return False
            if any("\n" in s.text for s in cell_spans):
                return False
        return True

    def _is_code_accumulator(row: list[list]) -> bool:
        """True if every non-empty cell is all-monospace (may have newlines)."""
        for cell_spans in row:
            text = "".join(s.text for s in cell_spans).strip()
            if not text:
                continue
            text_spans = [s for s in cell_spans if s.text.strip()]
            if not text_spans or not all(s.monospace for s in text_spans):
                return False
        return True

    merged: list[list[list]] = [rows[0]]
    for row in rows[1:]:
        if (_is_single_line_code_row(row)
                and len(merged) >= 2
                and _is_code_accumulator(merged[-1])):
            target = merged[-1]
            for ci in range(len(row)):
                if ci >= len(target):
                    break
                if row[ci]:
                    if target[ci]:
                        target[ci].append(Span(text="\n"))
                    target[ci].extend(row[ci])
        else:
            merged.append(row)
    return merged


def _classify_and_annotate(
    rows: list[list[list]],
) -> tuple[str, str, list[list[list]]]:
    """Classify rows, optionally merge, return (kind, strategy, rows)."""
    signals = _compute_table_signals(rows)
    kind = _classify_table(signals)
    strategy = _STRATEGY_MAP[kind]

    if kind == TableKind.CODE_COMPARISON:
        rows = _merge_code_rows(rows)

    # Pipe tables cannot represent multi-line cell content. If any cell
    # contains a newline, force HTML table rendering regardless of kind.
    if strategy == TableStrategy.PIPE_TABLE:
        for row in rows:
            for cell_spans in row:
                if any("\n" in s.text for s in cell_spans):
                    strategy = TableStrategy.HTML_TABLE
                    break
            if strategy == TableStrategy.HTML_TABLE:
                break

    return kind.value, strategy.value, rows


def _detect_header_block(blocks: list[Block], table_start_idx: int,
                         ref_cols: list[float], num_cols: int
                         ) -> list[list] | None:
    """Check block preceding a table for column headers (e.g. Before | After).

    Returns a header row (list of cell-span-lists) if found, None otherwise.
    """
    if table_start_idx == 0:
        return None

    prev_blk = blocks[table_start_idx - 1]
    first_table_blk = blocks[table_start_idx]

    # Must be same page and close vertically
    if prev_blk.page_num != first_table_blk.page_num:
        return None
    y_gap = first_table_blk.lines[0].bbox[1] - prev_blk.lines[-1].bbox[3]
    if y_gap > 30.0 or y_gap < 0:
        return None

    # Must have same number of lines as columns (one label per column)
    if len(prev_blk.lines) != num_cols:
        return None

    # Check x-positions match the table columns
    for li, line in enumerate(prev_blk.lines):
        if abs(line.bbox[0] - ref_cols[li]) > _COLUMN_X_TOLERANCE * 2:
            return None

    # Must be non-monospace short text (headers, not code)
    for line in prev_blk.lines:
        text = "".join(s.text for s in line.spans).strip()
        if len(text) > 30:
            return None
        if any(s.monospace for s in line.spans if s.text.strip()):
            return None

    # Build header row
    header_row = []
    for line in prev_blk.lines:
        header_row.append(list(line.spans))
    while len(header_row) < num_cols:
        header_row.append([])
    return header_row


def _filter_overlapping_mupdf_tables(
    page_mupdf_tables: dict[int, list[dict]],
    existing_sections: list[Section],
) -> dict[int, list[dict]]:
    """Remove find_tables entries that overlap with already-detected tables."""
    if not existing_sections:
        return page_mupdf_tables

    existing_ranges: list[tuple[int, float, float]] = []
    for sec in existing_sections:
        if not sec.lines:
            continue
        y_min = min(ln.bbox[1] for ln in sec.lines)
        y_max = max(ln.bbox[3] for ln in sec.lines)
        existing_ranges.append((sec.page_num, y_min, y_max))

    result: dict[int, list[dict]] = {}
    for pg, tables in page_mupdf_tables.items():
        kept = []
        for tbl in tables:
            bbox = tbl["bbox"]
            overlaps = False
            for epg, ey0, ey1 in existing_ranges:
                if pg != epg:
                    continue
                overlap = min(bbox[3], ey1) - max(bbox[1], ey0)
                if overlap > 0:
                    overlaps = True
                    break
            if not overlaps:
                kept.append(tbl)
        if kept:
            result[pg] = kept
    return result


def detect_tables(
    blocks: list[Block],
    *,
    page_mupdf_tables: dict[int, list[dict]] | None = None,
) -> tuple[list[Section], list[Block]]:
    """Detect table regions from MuPDF block structure.

    Returns (table_sections, remaining_blocks).
    Table sections have kind=TABLE with high confidence.
    Remaining blocks are the non-table blocks for normal processing.
    """
    column_xs = _find_column_xs(blocks)  # geometric second signal

    table_sections: list[Section] = []
    remaining: list[Block] = []
    i = 0

    while i < len(blocks):
        cols = _block_column_positions(blocks[i])
        if cols is None:
            remaining.append(blocks[i])
            i += 1
            continue

        table_blocks = [blocks[i]]
        # Track the "reference" column positions used for strict matching.
        # When a relaxed (column-count) match fires, adopt the new block's
        # positions as reference so subsequent data rows can strict-match
        # against each other.
        ref_cols = cols
        partial_absorbed: set[int] = set()  # id(block) for partial-row path
        j = i + 1
        while j < len(blocks):
            next_cols = _block_column_positions(blocks[j])
            if next_cols is not None and _columns_match(ref_cols, next_cols):
                table_blocks.append(blocks[j])
                j += 1
            elif (next_cols is not None
                  and _columns_count_match(
                      ref_cols, next_cols,
                      table_blocks[-1].bbox[3], blocks[j].bbox[1],
                      blocks[j].page_num == table_blocks[-1].page_num)):
                # Relaxed match: same column count, close proximity.
                # Adopt new positions as reference (data rows are more
                # consistent than centered headers).
                table_blocks.append(blocks[j])
                ref_cols = next_cols
                j += 1
            elif (_is_column_aligned_orphan(blocks[j], column_xs)
                  and j + 1 < len(blocks)
                  and blocks[j].page_num == table_blocks[-1].page_num):
                peek_cols = _block_column_positions(blocks[j + 1])
                if (peek_cols is not None
                        and _columns_match(ref_cols, peek_cols)
                        and blocks[j + 1].page_num == blocks[j].page_num):
                    table_blocks.append(blocks[j])
                    j += 1
                else:
                    break
            elif (len(table_blocks) >= 2
                  and _is_partial_row(blocks[j], ref_cols,
                                      table_blocks[-1].bbox[3],
                                      blocks[j].page_num
                                      == table_blocks[-1].page_num)):
                # Partial row: fewer columns than expected, but all
                # x-positions match known columns.  Only fires after
                # at least 2 full-column blocks so it extends an
                # established table, not a bare header.
                # The partial-row block itself is a new row, NOT a
                # continuation.  Only its trailing orphans merge into it.
                table_blocks.append(blocks[j])
                j += 1
                while (j < len(blocks)
                       and _is_column_aligned_orphan(blocks[j], column_xs)
                       and blocks[j].page_num
                           == table_blocks[-1].page_num):
                    partial_absorbed.add(id(blocks[j]))
                    table_blocks.append(blocks[j])
                    j += 1
            else:
                break

        # Absorb trailing continuations of the last row's non-first
        # columns.  These are single-line blocks whose x0 matches
        # column 1+ but have no following full-column row to trigger
        # the lookahead-based orphan absorption above.
        # Guard: only extend tables that are already well-established
        # (header + data rows) to avoid grabbing code-comparison content.
        if len(table_blocks) >= _MIN_TABLE_ROWS:
            while (j < len(blocks)
                   and _is_trailing_continuation(
                       blocks[j], ref_cols,
                       table_blocks[-1].bbox[3],
                       blocks[j].page_num == table_blocks[-1].page_num)):
                partial_absorbed.add(id(blocks[j]))
                table_blocks.append(blocks[j])
                j += 1

        if len(table_blocks) >= _MIN_TABLE_ROWS:
            num_cols = len(ref_cols)
            rows: list[list[list]] = []
            all_lines = []

            # Header detection: check block before table for column headers
            header_row = _detect_header_block(blocks, i, ref_cols, num_cols)
            if header_row is not None:
                rows.append(header_row)

            # Track which row indices come from the partial-row
            # absorption path so the backward-merge pass absorbs them
            # into the preceding data row.
            continuation_row_indices: set[int] = set()

            for blk in table_blocks:
                from_partial = id(blk) in partial_absorbed
                blk_cols = _block_column_positions(blk)
                if blk_cols is None:
                    blk_cols = ref_cols

                if from_partial:
                    row: list[list] = [[] for _ in range(num_cols)]
                    for line in blk.lines:
                        all_lines.append(line)
                        best_col = min(
                            range(num_cols),
                            key=lambda ci: abs(line.bbox[0] - ref_cols[ci]),
                        )
                        if row[best_col] and line.spans:
                            row[best_col].append(Span(text=" "))
                        row[best_col].extend(line.spans)
                    continuation_row_indices.add(len(rows))
                else:
                    row = []
                    for line in blk.lines[:num_cols]:
                        row.append(list(line.spans))
                        all_lines.append(line)
                    while len(row) < num_cols:
                        row.append([])
                    for line in blk.lines[num_cols:]:
                        all_lines.append(line)
                        line_x = line.bbox[0]
                        best_col = min(
                            range(num_cols),
                            key=lambda ci: abs(line_x - blk_cols[ci]),
                        )
                        if row[best_col] and line.spans:
                            row[best_col].append(Span(text="\n"))
                        row[best_col].extend(line.spans)
                rows.append(row)

            # Pass A: merge continuation rows (from partial-row blocks)
            # backward into the preceding row.
            if continuation_row_indices:
                tmp: list[list[list]] = []
                for ri, row in enumerate(rows):
                    if ri in continuation_row_indices and tmp:
                        target = tmp[-1]
                        for ci in range(num_cols):
                            if not row[ci]:
                                continue
                            if target[ci]:
                                target[ci].append(Span(text=" "))
                            target[ci].extend(row[ci])
                    else:
                        tmp.append(row)
                rows = tmp

            # Pass B: merge forward-orphans (single populated first
            # cell) into the following row.  This handles wrapped cell
            # first lines absorbed by the existing orphan-lookahead.
            merged: list[list[list]] = []
            k = 0
            while k < len(rows):
                row = rows[k]
                if (k + 1 < len(rows)
                        and bool(row[0])
                        and all(not cell for cell in row[1:])
                        and bool(rows[k + 1][0])):
                    sep = [Span(text="\n")]
                    merged.append(
                        [row[0] + sep + rows[k + 1][0]]
                        + rows[k + 1][1:])
                    k += 2
                else:
                    merged.append(row)
                    k += 1
            rows = merged

            kind_val, strategy_val, rows = _classify_and_annotate(rows)
            text = _render_table_text(rows)

            table_sections.append(Section(
                kind=SectionKind.TABLE,
                text=text,
                confidence=Confidence.HIGH,
                lines=all_lines,
                page_num=table_blocks[0].page_num,
                columns=rows,
                table_kind=kind_val,
                table_strategy=strategy_val,
            ))
            _log.debug("Table detected: %d rows x %d cols on page %d",
                        len(rows), num_cols, table_blocks[0].page_num)
            i = j
        else:
            remaining.append(blocks[i])
            i += 1

    # Pass 2: side-by-side block tables on remaining blocks
    sbs_tables, sbs_used = _detect_side_by_side_tables(remaining)
    if sbs_tables:
        table_sections.extend(sbs_tables)
        remaining = [b for idx, b in enumerate(remaining)
                     if idx not in sbs_used]

    # Pass 3: narrow horizontal-row tables (e.g. vote/poll grids)
    hr_tables, hr_used = _detect_horizontal_row_tables(remaining)
    if hr_tables:
        table_sections.extend(hr_tables)
        remaining = [b for idx, b in enumerate(remaining)
                     if idx not in hr_used]

    # Pass 4: MuPDF native find_tables() on remaining blocks.
    # Runs last so it only catches tables missed by all heuristic passes.
    filtered_mupdf_tables = _filter_overlapping_mupdf_tables(
        page_mupdf_tables or {}, table_sections)
    mupdf_tables, mupdf_used = _detect_mupdf_native_tables(
        remaining, filtered_mupdf_tables)
    if mupdf_tables:
        table_sections.extend(mupdf_tables)
        remaining = [b for idx, b in enumerate(remaining)
                     if idx not in mupdf_used]

    if table_sections:
        kinds = {}
        for sec in table_sections:
            kinds[sec.table_kind] = kinds.get(sec.table_kind, 0) + 1
        _log.info("Table classification: %s", dict(sorted(kinds.items())))

    return table_sections, remaining


def exclude_table_regions(blocks: list[Block],
                          table_sections: list[Section]) -> list[Block]:
    """Remove blocks whose vertical midpoint falls within a detected table region."""
    if not table_sections:
        return blocks

    table_ranges = []
    for sec in table_sections:
        if not sec.lines:
            continue
        y_min = min(ln.bbox[1] for ln in sec.lines)
        y_max = max(ln.bbox[3] for ln in sec.lines)
        table_ranges.append((sec.page_num, y_min, y_max))

    result = []
    for block in blocks:
        in_table = False
        by = (block.bbox[1] + block.bbox[3]) / 2.0
        for pg, y_min, y_max in table_ranges:
            if (block.page_num == pg
                    and y_min - _TABLE_Y_OVERLAP_MARGIN <= by
                    <= y_max + _TABLE_Y_OVERLAP_MARGIN):
                in_table = True
                break
        if not in_table:
            result.append(block)
    return result
