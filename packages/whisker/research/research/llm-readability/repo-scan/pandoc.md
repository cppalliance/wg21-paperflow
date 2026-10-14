# Repo scan: pandoc (LLM-readability verification)

**Repo:** `packages/whisker/research/repos/pandoc` (shallow clone, read-only)  
**Scan date:** 2026-07-06  
**Question:** Does pandoc verify that converter output is LLM-readable (comprehension, fact assertions, LLM eval, downstream consumability)?

## Does it verify LLM-readability?

**No.** Pandoc gates **structural fidelity** (byte-exact goldens, AST equality, QuickCheck round-trips on internal representations). It has **zero** fact-assertion benchmarks, LLM-as-judge lanes, downstream QA tracks, or comprehension corpora. Round-trip idempotence exists, but on **Pandoc AST / HTML AST**, not on "can an LLM recover facts from emitted markdown."

---

## Findings

1. **[HIGH] Three regression layers, all structural — no comprehension lane.** Command integration tests auto-discover `test/command/*.md` (1,078 fixture files at scan time) and compare stdout to embedded goldens after `^D` with exact string equality (`test/Tests/Command.hs:83-87`, `117-118`). Reader/writer suites use committed `.native` AST goldens (255 files under `test/`) via `goldenTest` with `\r` stripping before diff (`test/Tests/Old.hs:381-403`, `test/Tests/Helpers.hs:70-85`). QuickCheck properties cover Native writer, XML, HTML reader, and annotated-table invariants (`test/Tests/Writers/Native.hs:10-21`, `test/Tests/XML.hs:24-28`, `test/Tests/Readers/HTML.hs:47-56`, `141-144`, `test/Tests/Writers/AnnotatedTable.hs:137-151`). Repo-wide grep for `comprehension`, `LLM`, `fact assert`, `downstream`, `readability`, `benchmark` under `test/` returned **no matches**.

2. **[HIGH] Round-trip idempotence exists — but not on markdown LLM output.** Native AST: `read (writeNative d) == d` (`test/Tests/Writers/Native.hs:10-12`). XML AST: `writeXML >=> readXML` identity (`test/Tests/XML.hs:24-25`). HTML reader: `readHtml . writeHtml5String` on sanitized blocks (`test/Tests/Readers/HTML.hs:47-56`, `141-144`), with explicit stubs for tables/code/raw blocks that would break RT (`test/Tests/Readers/HTML.hs:33-40`). **Markdown round-trip QuickCheck is commented out** because "the round-trip properties frequently fail" (`test/Tests/Readers/Markdown.hs:151-162`, `452-455`). A handful of command fixtures label "round trip" but still gate **golden stdout equality**, not parse→render→parse identity (e.g. `test/command/tasklist.md:96-104`).

3. **[MED] Operating point is exact match after normalization — no ROC, no LLM judge.** Golden compare is `expected == actual` with deterministic normalizers (`test/Tests/Old.hs:402-403`, `test/Tests/Helpers.hs:79-85`). Refresh is local `--accept`, never CI-auto (`Makefile:50-51`, `CONTRIBUTING.md:272-275`). This is the opposite of olmOCR-style fact assertions (Q1/Q3 baseline): pandoc proves formatting contracts, not semantic recoverability.

4. **[MED] Command tests also gate exit codes and stderr.** Failed runs append `=> N` to captured output (`test/Tests/Command.hs:67-69`); expected warnings are prefixed `2> ` in goldens. Whisker guard has no equivalent exit-code or warning-log regression gate (redteam §4, confirmed here).

5. **[LOW] Downstream consumability is out of scope.** Unlike olmOCR's continued-pretraining lift (Q3 card) or RealDocBench field QA, pandoc never feeds output to a fixed reader LLM or fact checker. The closest "consumability" signal is internal AST round-trip, which does not test markdown table neighbor relations, math surfaces, or reading-order facts that Lane 3 checks.

---

## Portable to whisker (concrete, ranked)

1. **Exact golden micro-corpus beneath metric slack (Lane 1 extension).** Pandoc's primary gate is committed full output after normalization, not derived scores. Map to `whisker/goldens/<fixture>.expected.md` with `\r`/LF policy documented at the diff boundary — already recommended in redteam §1.1, confirmed as pandoc's load-bearing pattern.

2. **Fail-closed fixture discovery.** New `test/command/*.md` blocks and new `.native` pairs must ship committed expected output or CI fails (`Command.hs:83-87`, `Old.hs:370-394`). Map to: new corpus pids or comprehension facts require explicit `--update`/PR acknowledgment; no silent `STATUS_NEW` pass.

3. **Pre-diff normalization contract in the baseline file.** Pandoc embeds the contract in goldens + normalizer functions (`Old.hs:389-391`, OOXML timestamp whitelists per redteam). Whisker should read committed `axis_slack`/`floors` from baseline JSON when present (redteam bug table, still open).

4. **Multi-layer regression (golden + property + integration).** Pandoc runs command, file golden, unit AST, and QuickCheck layers in parallel. Whisker should add at least one property/meta-test on guard/metric normalization (analogous to `p_write_rt`, `propBuilderAnnTable`) — not a substitute for Lane 3 facts.

5. **Round-trip idempotence — partially portable, honest ceiling.** **Portable:** AST-level or internal-representation RT (pandoc Native/XML/HTML QC). **Not portable as LLM-readability proof:** markdown RT is disabled in pandoc itself; WG21 markdown is lossy and reflow-sensitive. Whisker could explore `convert → parse_md → structural_invariants` on a **tiny** fixture set, but must not treat it as comprehension. Lane 3 fact assertions remain the only proven LLM-readability pattern in our stack (00-baseline).

6. **Not portable:** LLM-as-judge, fact JSONL corpora, downstream extraction QA — pandoc does not implement these.

---

## Cross-check vs redteam report (`packages/whisker/research/redteam/pandoc.md`)

| Redteam claim | Scan verdict | Evidence |
|---------------|--------------|----------|
| Golden-file / command-test QA, byte-exact after normalization | **Confirmed** | `Old.hs:402-403`, `Command.hs:117-118`, `Helpers.hs:79-85` |
| ~1,760 command tests in `test/command/*.md` | **Partially confirmed** | 1,078 `.md` fixture files; individual `% pandoc` code blocks sum to ~1,700+ (many files have multiple blocks) |
| ~255+ `.native` AST goldens | **Confirmed** | 255 `.native` files counted under `test/` |
| QuickCheck round-trip on Native (`read (writeNative d) == d`) | **Confirmed** | `Native.hs:10-12` |
| No comprehension / LLM-readability testing | **Confirmed** | No matching tests or docs; all gates are structural |
| Multi-layer regression (command + golden + QC) | **Confirmed** | See Findings §1 |
| `--accept` refresh, CI never auto-accepts | **Confirmed** | `Makefile:50-51`, `CONTRIBUTING.md:272-275` |
| Round-trip as whisker gap | **Confirmed with nuance** | RT exists for AST/XML/HTML; **markdown RT QC disabled** (`Markdown.hs:452-455`) — redteam cites Native RT but scan adds that markdown-output RT is explicitly abandoned |
| Redteam scope is guard/calibrate, not LLM-readability | **Confirmed** | Redteam findings align with structural QA; this scan adds the explicit **no LLM-readability** verdict for Wave 2 |

**New vs redteam:** Markdown round-trip property disabled; HTML round-trip uses sanitized stubs (tables → placeholder) so it does not validate table markdown consumability; command-test count clarified as 1,078 files vs ~1,760 blocks.
