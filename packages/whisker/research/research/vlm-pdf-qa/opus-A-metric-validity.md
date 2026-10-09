# opus-A - Metric / Measurement Validity Re-verification

**Meta-reviewer A (measurement/metric validity). Date: 2026-07-07.**
Mandate: re-derive every quantitative claim in `27-page-rasterization-engineer.md`,
`29-token-budget-economist.md`, `33-cost-latency-analyst.md`, `14-false-pass-hunter.md`
against the actual code/files, not the personas' word. All numbers below were reproduced
this run. Reproduction harness: `uv run --package tomd python` (PyMuPDF 1.27.2.3, Qwen
`smart_resize` reimplemented), plus `Get-ChildItem` counts and direct reads of
`packages/whisker/research/repos/olmocr/`. The `data/` tree is Read-denied to the tool;
all `data/` numbers were produced by a scripted PyMuPDF/JSON pass over the real files.

Verdicts: **VERIFIED** (reproduced within rounding), **CORRECTED** (number or framing
wrong / conditional), **DROPPED** (cannot reproduce from repo evidence; downgrade).

---

## VERIFIED (reproduced within rounding)

1. **Corpus = 189 PDFs, 6,266 pages.** VERIFIED exactly.
   Evidence: `Get-ChildItem data\paperstore\*.pdf` = 189; all 189 in `data/` are under
   `paperstore/` (matches `00-baseline.md:80`). `fitz.page_count` over all 189 →
   `total_pages = 6266` (matches `29:47`, `33:10`). min 1 / median 11 / mean 33.15 / max 2679.
   The `≤50-page subset` median 10.5 that `33:10` cites also reproduces exactly
   (n=178, median 10.5, mean 13.46).

2. **det sidecars tag only ~1.9% of pages.** VERIFIED at **1.92%**.
   Evidence: 381 `*.whisker.json` under `data/whisker/det/`. Region lists are exactly two
   fields, `missing_regions` + `extra_regions` (n5036 top-level keys confirm). Across all
   381: **777** region rows carry a `page` key; **598 are `page: null`**, 179 non-null;
   **92/381** sidecars have ≥1 non-null page tag; **120** distinct (pid,page) flagged =
   `120/6266 = 1.92%`. Every sub-number in `29:77` (120/6266=1.9%, 598/777 null, 92/381)
   reproduces to the digit. Caveat I add: the 381 det sidecars span HTML papers (no page
   concept) and revisions without a staged PDF, so 6,266 (PDF pages only) is a slightly
   generous denominator; the conclusion (det page-tags are a rounding error, cannot drive
   coverage) stands regardless.

3. **olmocr rasterization facts.** VERIFIED.
   `renderpdf.py:39` default `target_longest_image_dim=2048`; `:52` scale
   `= target_longest * 72 / longest_dim` (longest side → exactly target px); `:63` webp
   wrapper default 1024. `pipeline.py:1229` runtime default **1288**. `build_page_query`
   `MAX_TOKENS=8000` (`:107`), content parts = text + `image_url data:image/png;base64`
   (`:133-146`), `temperature=0.0` (`:145`). `MODEL_MAX_CONTEXT=16384` (`:162`).
   All match `00-baseline.md:14-19` and the persona tables.

4. **A4 DPI / pixel geometry.** VERIFIED.
   longest side = 841.68 pt. `target=1288 → dpi 110.18 → 911×1288`; `target=1684 → dpi
   144.05 → 1191×1684`; `target=2048 → dpi 175.19 → 1449×2048`. Matches `27:22-24`
   (1288→110.18/911×1288; 1684→144.00/1191×1683) and `14:8` (110.14 DPI/910×1288; the
   0.04-DPI/1-px drift is 842 vs 841.68 pt rounding).

5. **Stroke-legibility arithmetic (at the render, before the server).** VERIFIED.
   `stroke_px = dpi/72`: 1288 → **1.53** px/pt; 1684 → **2.00** px/pt; 192-DPI marker → 2.67.
   9 pt monospace char (~0.6 em = 5.4 pt) at 110 DPI = **8.26 px/char** ≈ `14:8`'s "~8.3".
   Matches `27:33-36`. (But see CORRECTED #2 — this is the render, not what the model sees.)

6. **Qwen3-VL naive 32×32 token count @1288 = 1,189.** VERIFIED.
   `ceil(1288/32)*ceil(911/32) = 41*29 = 1189` (matches `27:28`); raw pixels 1.17 M sits
   inside the 262,144–1,310,720 band (`05-web.md:55`). Confirmed by script.

7. **olmocr has NO in-repo throughput (tok/s or pages/s) figure; cost is "<$200 / 1M pages".**
   VERIFIED. README:36 "less than $200 USD per million pages"; no s/page or tok/s anywhere
   in README. `29:66` states this correctly. This directly undercuts every wall-clock number
   built on external latency anchors (see DROPPED #1).

8. **md ≈ 2 k chars/page.** VERIFIED (minor). My run: median **2,048** / mean 2,159 chars
   per page across 183 matched md↔pdf pairs. `29:26` said median 2,090 / mean 2,204 — 2%
   high (likely a slightly different page-count join); immaterial to the token totals.

---

## CORRECTED (number or framing wrong, or unstated governing variable)

1. **Qwen2.5-VL visual-token count is a DEPLOYMENT variable, not a fixed number — both
   personas hard-coded opposite assumptions.**
   - `27:26` states 1288 px → **1,518** tokens (`46×33`), computed with **no** `max_pixels`
     cap, and uses it to claim 1288 "overshoots Qwen2.5-VL's recommended band."
   - `29:13` states 1288 px → raw 1,497 → **capped to 1,280** (`1280×28×28` default).
   - REALITY (reproduced): with the generic Qwen2.5-VL default `max_pixels = 1280·28·28 =
     1,003,520`, `smart_resize` downscales 911×1288 (1.17 M px) to **840×1176 → 1,260
     tokens**. Uncapped, it is **1,497** (raw px / 784). So `29`'s ~1,280 and `27`'s ~1,518
     are each correct *only under their unstated cap assumption*.
   - Which one applies to olmocr? I grepped the olmocr pipeline: it sets **no**
     `max_pixels`/`min_pixels` (only `bench/runners/run_dotsocr.py` references them, default
     `None`). olmocr renders at 1288 px (1.17 M) and relies on the *served* model's
     `preprocessor_config.json`. Since olmocr clearly intends the model to see 1288 px, its
     served cap must be **> 1.003 M**, i.e. olmocr-style deployment → ~1,497–1,518 tokens
     (`27` closer), NOT 1,260 (`29` closer). **Correction: report the served `max_pixels`
     as the governing input; ~1,260 (generic default) and ~1,500 (olmocr-style) are both
     valid, ~1,518 as a universal fact is not.**

2. **CRITICAL: "1684 px / 144 DPI gives 2 px/stroke legibility" is FALSE under default
   serving — the headline error.** `27:38,74` recommends 1684 px longest side "to meet the
   ≥2 px/pt stroke floor for 9–10 pt body/code." But I reproduced that under the generic
   default `max_pixels` (1.003 M), **1288, 1684, and 2048 px client renders ALL collapse to
   the same 840×1176 grid** (script output: identical `resized=840x1176 tok=1260` for all
   three). 840×1176 on A4 = **~100 DPI effective, stroke_px ≈ 1.40** — *worse* than the
   1.53 the persona ascribes to 1288, and nowhere near 2.0. So rendering above ~1024 px is
   wasted unless the server `max_pixels` is also raised, and `05-web.md:52` says per-request
   `max_pixels` is ignored under vLLM. To actually obtain 144-DPI legibility you must raise
   the server cap to ≥ ~2.0 M px, which then costs ~2,014 tokens (Qwen3 32-grid) up from
   1,189 — i.e. **legibility is not free; it is exactly the token cost `29` warned about.**
   `27`'s legibility argument and `29`'s cost argument are the same coupled tradeoff; neither
   persona connected them. Net: the false-pass risk `14`/`27` describe at "1288 px" is real
   but should be stated at the **model-visible ~100 DPI / 840×1176**, and the fix is a
   server-cap change with a measured token cost, not a client render-size bump.

3. **Wall-clock denominator (6,266 pages) is ~50% two atypical mega-documents.** The 21–56 h
   (`29:88`) and ~21 h (`33:10`) corpus projections treat all 6,266 pages as equivalent WG21
   QA work. Reproduced page census: **n5046.pdf = 2,679 pages (42.8% of the entire corpus)**
   and **p3839r0.pdf = 423** — together **3,102 pages = 49.5%**. These are standard-draft /
   register-scale documents, not proposals (median proposal = 11 pages). Excluding just those
   two: 3,164 pages → at 12 s/page **≈ 10.5 h**, not 20.9 h. **Correction: the "every page"
   wall-clock is real but dominated by 2 non-proposal docs; the operationally relevant figure
   for typical papers is roughly half.** `33:10` half-acknowledges this ("2679-page PDF alone
   = 8.9 h") but still headlines the blended 20.9 h.

4. **Low-res 728 px = "478 visual tokens" → actually ~468 after gridding.** `29:12` uses raw
   px/784 = 478; `smart_resize` to the 28-grid gives 504×728 → **468** (−2%). Trivial, but
   the token table is raw-pixel arithmetic, not the gridded count the server actually bills.

---

## DROPPED (cannot reproduce from repo; downgrade confidence)

1. **Per-page latency anchors behind the wall-clock bands are external and unverifiable.**
   `33:12,14` build 8–20 s/page from: olmocr "dense 28.7 s/page, sparse 5.6 s/page"
   (canemah.org archive), PR#316 "10–20 pages/s", Issue#155 "0.33–0.67 img/s". None are in
   the repo (VERIFIED #7: olmocr ships no latency number), and I cannot fetch those links to
   confirm. `29`'s "2 s prefill + 600-tok decode @ 20/40/60 tok/s" is explicitly self-labeled
   assumption. **Downgrade: the 13–56 h band is an order-of-magnitude ESTIMATE with no
   measured per-page latency; treat as ±2× (as `29:102`/`33:34` themselves concede), not a
   plannable figure.** One repo fact *does* strengthen the *direction*: olmocr defaults
   `--workers 20`, `--max_concurrent_requests 1600` (`pipeline.py:1223-1224`) — its published
   throughput is massively parallel, so a D11-serial (1 in-flight) whisker lane is legitimately
   far slower than any olmocr headline rate; the regression sign is safe, the magnitude is not.

2. **olmocr "12–20% retry" amplification (`33:18`).** Repo shows `--max_page_retries` default
   **8** and `--max_page_error_rate` default **0.004** (`pipeline.py:1221-1222`) — a retry
   *budget*, not an observed rate. The 12–20% observed-retry figure is external (Issue #424 /
   paper Table 6), not reproducible here. **Downgrade to unverified.**

---

## Bottom line for the swarm

The corpus (189/6,266) and the det-coverage (1.92%) claims are rock-solid — build on them.
The visual-token and DPI numbers are arithmetically fine but were reported without the one
variable that decides them (served `max_pixels`); the practical consequence is that the
"1684 px for legibility" recommendation is inert under default serving and only works as a
deliberate, token-costly server-cap change. The wall-clock bands are directionally right
(serial VLM ≫ today's one-call text lane) but rest on unverifiable external latency anchors
and a denominator half-composed of two non-proposal mega-docs; treat them as estimates.
