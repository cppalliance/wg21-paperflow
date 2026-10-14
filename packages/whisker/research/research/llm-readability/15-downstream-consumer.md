# 15 - Downstream-Consumer

**Verdict:** usable-with-conditions — Lane 3 certifies full-document fact recovery on two papers, but the live consumers (assay claim extraction + agora thread planning) read markdown through chunked, line-windowed, text-only views that the gate never exercises; a whisker-pass paper can still yield misread claims or hollow agora plans.
**Confidence:** high

## Findings

- [CRITICAL] Lane 3 evaluates the whole `paper.md`; assay never loads the whole document into an LLM call. Evidence: `facts.py:309-335` runs table neighbor checks over full markdown; assay Step 3 chunks via `chunk_paper` (`assay/pipeline.py:525-528`, `assay/chunker.py:44-86`) and Steps 4–5 inject only `format_numbered_lines(..., chunk.start_line, chunk.end_line)` per chunk (`assay/pipeline.py:208-212`, `:645`). Impact: a conversion can pass every verified `table` fact while a chunked extractor sees only the header rows of a wide table coalesced into an oversized section, mislabeling comparative claims agora later treats as ground truth (`agora/pipeline.py:177-182`).

- [HIGH] Chunking is not table-atomic, contradicting the MDKeyChunker pattern cited in research. Evidence: `assay/chunker.py:152-174` recurses into child headings or splits on bold-numbered subsections with no pipe-table guard; `assay/rag.py:133-159` splits oversized sections on `\n\n+` paragraph boundaries (pipe-table rows are single-newline separated, so an entire table is one paragraph and can still be truncated against a char budget). Impact: table rows and header/body associations can straddle chunk seams; Lane 3 neighbor checks on the intact grid do not predict per-chunk LLM comprehension (TabVerse mean cell lookup 9.9%, https://arxiv.org/html/2606.09578v1).

- [HIGH] Image semantics are text-only for consumers; Lane 3 has no `image-ref` fact type. Evidence: tomd emits `![alt](path)` (`tomd/lib/pdf/emit.py:1296-1309`); baseline lists missing image/code/xref fact types (`00-baseline.md:80-83`); assay and agora pass markdown strings to LLMs with no image bytes (`assay/pipeline.py:588-596`, `agora/pipeline.py:268`). Impact: figure-heavy papers can pass Lane 3 on prose/table/math while downstream pipelines treat figures as alt-text plus a filesystem path they never fetch; agora Smell Test still dumps raw `paper_source` including those refs (`agora/pipeline.py:268`).

- [MED] Front matter is handled inconsistently across the stack. Evidence: assay blanks YAML fences but keeps line numbers (`assay/blanking.py:187-210`, `assay/pipeline.py:461`); agora routes subreddit from paperstore `meta.target_group`, populated at convert from tomd audience (`agora/pipeline.py:160-166`, `cli/orchestrator.py:67-68`, `tomd/lib/metadata_yaml/extract.py:88`), not by re-parsing YAML at runtime; agora Step 1 injects unblanked `paper_source` including front matter (`agora/pipeline.py:149-157`, `:268`). Impact: Lane 3 `present`/`order` facts on body text do not certify that agora's LLM pass sees the same surface assay analyzed; duplicate/conflicting audience signals (DB meta vs YAML block) can steer routing without failing comprehension CI.

- [MED] The documented `read_paper` 500-line cap is real but unused on the assay citation path that actually ships. Evidence: `pipeline/tools.py:70,83-96` clamps `num_lines` to 500 and re-wraps each slice; `assay/assay.md:251` instructs Verify to use `make_read_paper_tool`, but `_verify_against_one_companion` wires `_make_explore_paper_tool` with semantic RAG slices instead (`assay/pipeline.py:978-1002`, `:166-189`). Impact: integrators following the authority doc expect line-browse semantics and boundary math for long tables; production uses embedding hits that can return non-contiguous line ranges and omit rows between hits, with no test tying either path to Lane 3 table facts.

- [MED] Cross-chunk reconciliation is partial. Evidence: `_cross_chunk_decide` re-pairs unsupported claims with evidence quotes across chunks (`assay/pipeline.py:688-752`) but does not re-evaluate table structure or re-run extraction; it emits plain XML-ish blocks without `inject_untrusted` wrapping (`assay/pipeline.py:736-752`). Impact: mitigates one failure mode (evidence in chunk B supports claim in chunk A) but leaves table-spanning and figure-backed claims uncorrected; a Lane 3 pass still allows agora to plan from incomplete assay artifacts.

- [LOW] Agora consumes assay outputs under legacy `dissect_*` field names; `packages/dissect/` is absent at this SHA, replaced by `assay` CLI (`cli/__main__.py:44`, `agora/models.py:391-398`). Evidence: `agora/pipeline.py:710` docstring still says "dissected"; `get_claims` returns empty when assay has not run (`sqlite_backend.py:1382-1386`) without blocking agora. Impact: operational trap — whisker certifies markdown, agora runs on empty claims/evidence and leans on raw `paper_source`, looking successful while bypassing the intended two-stage fidelity chain.

## False-pass hypothesis

P4182R0-class paper: Lane 3 passes two verified `table` neighbor facts on the full grid (`00-baseline.md:53-57`, `facts.py:309-335`). A regression swaps two body cells in a large comparison table while preserving the two asserted cells and all `present` strings. Assay coalesces the table section into one chunk over the token budget; Extract records benchmark claims from visible rows only; Decide marks them supported within the chunk; cross-chunk Decide never fires because evidence lines sit in the same chunk. Whisker CI stays green; agora Smell Test emits anchors from corrupted claims JSON plus raw markdown that no longer matches the table facts the gate checked.

## False-fail hypothesis

none found — consumers are more permissive than Lane 3 (chunk-local partial reads, empty assay artifacts tolerated, agora raw markdown fallback). The failure direction is false-pass, not false-fail.

## What would change my mind

A comprehension corpus member with verified facts authored on chunk-sliced inputs matching assay's `chunk_paper` boundaries (including a multi-row table split across two chunks), plus a CI test that fails if table neighbor facts pass on full md but per-chunk `format_numbered_lines` slices lose any verified cell.
