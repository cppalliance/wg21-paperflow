# whisker

## Opening

Whisker scores a tomd conversion of a WG21 paper and tells a CI job whether the markdown is safe to ship, needs a person, or is broken. That decision comes from structural checks and a content-coverage floor, so a model outage or a model change cannot move the gate. An optional advisory lane can still mark where a person should look. After this page you can score a paper, read the line, run the three corpus checks, and tell a hard failure from a pass that only means no gate fired.

## What you are running

You run whisker against markdown that tomd has already written into a paperstore. A paper id (PID) such as `P3181R1` names one paper. The default install is a Python 3.12+ package with no LLM stack. The console script for scoring is `whisker`.

### A deterministic verdict

A scoring run prints one of three verdicts: `pass`, `review`, or `not-llm-readable`. The third is the hard fail. Summary sections use the name `not-llm-readable`, and the footer counts those papers as failed. `--gate` has no verdict literally named `fail`. A pass means no gate fired. It does not mean the conversion is correct. Table-readability certification is a separate axis. It is not this verdict.

### Three lanes that do not stand in for each other

Stability asks whether the normalized markdown changed against the committed `<pid>.expected.md` snapshot. Fidelity asks how close the markdown is to a human-corrected `<pid>.gt.md`, on text similarity (nid), table similarity (teds), and heading similarity (mhs). Comprehension asks whether source-verified facts in `<pid>.facts.jsonl` are still recoverable, with no LLM in that scoring loop. Each lane answers its own question. A green score does not answer them, and a green lane does not answer the other two.

### An advisory lane that cannot pass a paper

`whisker-tapetum-llm` is an opt-in second opinion on whether the conversion faithfully renders the source PDF or HTML. It may record that opinion, and a merged view may lower a deterministic pass to review. It is never allowed to rewrite the deterministic verdict, never allowed to change `whisker --gate`, and never allowed to turn `not-llm-readable` into `pass`. The two advisory console scripts, `whisker-tapetum-llm` and `whisker-readback`, install with the `tapetum-llm` extra.

## Install and a first score

The default install is enough for every deterministic command below. Point `$WG21_DATA_DIR` at the paperstore that already holds converted markdown. Papers that were never converted are skipped. When none are converted, whisker logs `no converted papers found; run 'paperflow convert' first` and stops with an error.

Score one paper. The default run also compares tomd with the markitdown oracle:

```text
whisker P3181R1
```

A paper that is not a clean pass shows a line like this. Passes are omitted until you ask for them, which the next section covers.

```text
P3181R1  ovr=0.884 nid=0.697 teds=1.000 mhs=0.955  <flags>
```

`P3181R1` is the paper id. `ovr` is the overall agreement with the oracle, the mean of the three numbers that follow. `nid` is text similarity. Here `0.697` is below the advisory edge `0.85`, so the paper is `review`. That disagreement never by itself makes the paper `not-llm-readable`. `teds` is table similarity. `mhs` is heading similarity. Both are reported on this line. The trailing field is the flag list: hard flags, then soft flags, or the word `clean`.

From this repo, run the same command through the package:

```text
uv run --package whisker whisker P3181R1
```

Omit `--workspace` and whisker uses `$WG21_DATA_DIR`. Pass `--workspace DIR` to score a different paperstore for that one invocation.

## Reading the score

The default summary is a triage list. It hides passes, then prints a `not-llm-readable (N)` section and a `review (N)` section. Each section shows at most 15 papers. Past that cap it prints `... and N more (see <path>)`, and that path is the `report.md` just written, by default `$WG21_DATA_DIR/whisker/det/report.md`. Papers are ordered lowest unigram coverage first.

With the oracle left on, which is the default, a review line leads with the oracle fields and does not lead with coverage:

```text
whisker P3181R1
```

```text
P3181R1  ovr=0.884 nid=0.697 teds=1.000 mhs=0.955  <flags>
```

Turn the oracle off and the same summary slot prints the content figures instead. `markitdown` is not run:

```text
whisker --no-reference P3181R1
```

```text
P3181R1  uni=... cov=... drift=... qa=<integer>
```

`qa` is an integer score, not a fraction. When a golden ideal exists for the paper, the same line also carries `idl=` (agreement with that ideal) and `gc=<composite>/<worst axis>` (which construct diverged most).

`uni` is unigram coverage. It is the coverage number that can fail or review the paper. `cov` is order-sensitive shingle coverage. It is context, and it never gates. `drift` is the drift figure printed beside them. Drift above `0.10`, tokens present in the markdown and absent from the source, is a soft flag. Order-sensitive shingle drift does not gate. `qa` is tomd's structural QA score. A score below `70` is a soft flag.

The run ends with a footer such as `=== 1 failed, 1 review, 1 passed (3 scored) in 12.5s ===`. A non-zero skip count or error count is inserted into that line. Then this sentence:

```text
"passed" means no gate fired, not that the conversion is correct.
```

That sentence is on the default summary and on the verbose summary.

Show every paper, including passes, lift the 15-line cap, and add up to five missing or extra region snippets of about 60 characters:

```text
whisker --all -v
```

A region snippet looks like `p.7: "missing chunk on page seven"`. Those snippets stay off the default summary.

Print only the one-line footer. This form leaves out the per-paper sections and leaves out the pass sentence. `-v` together with `-q` is a parser error:

```text
whisker --all -q
```

The quiet line is a single `=== ... ===` row.

Count hard and soft flags by category, rather than one row per numeric threshold:

```text
whisker --all --stats
```

The rollup is labeled `flag rollup`, with a `hard` count and a `soft` count.

For a script, `whisker --all --json` prints a JSON array on stdout and suppresses the human summary. Progress stays on stderr, and it is suppressed when stdout is piped, so the JSON stream stays intact. `--no-write` scores without touching the report files.

## The three lanes, in use

Run each lane against a corpus directory. The committed corpus in this repo is `packages/whisker/corpus`. Filenames match without regard to case, and paper ids are normalized to uppercase.

### Stability

```text
whisker golden --corpus packages/whisker/corpus
```

This compares each paper's normalized markdown to `<pid>.expected.md`. A change prints `FAIL {pid} [changed] N diff line(s)`. The footer reads `whisker golden: CHANGED over N paper(s)` or `whisker golden: stable over N paper(s)`, followed by a rollup in parentheses. This is the lane that catches a silent regression and a silent improvement, including a markdown edit that leaves the score verdict where it was. A paper that has `<pid>.gt.md` and no snapshot yet is `new`, and it passes until you pass `--fail-on-new`, which exits `5`. After you have read the diff, bless the current normalized markdown in place:

```text
whisker golden --corpus packages/whisker/corpus --update
```

`--update` writes the existing expected file and refuses to write through a symlink. A paper that only has `<pid>.gt.md` gets its first `<pid>.expected.md` from `--update`. The ground-truth file is left untouched.

### Fidelity

```text
whisker guard --corpus packages/whisker/corpus --baseline <file>
```

The baseline file is the committed per-paper guard baseline. The lane measures the conversion against `<pid>.gt.md`. Guard watches nid, teds, mhs, content recall, overall, and structural parity. One paper that drops more than `0.02` on any of those axes fails the run even when the corpus average holds. A drop equal to `0.02` still passes. A paper that crosses a published floor downward fails even when the drop is inside that slack. The same command fails when a phrase in `<pid>.anchors.json` vanishes, or a verified fact in `<pid>.facts.jsonl` fails, even though the numeric axes held. The stored baseline carries its own slack and floors. A baseline saved under an older schema than the current schema version, `10`, has to be regenerated:

```text
whisker guard --corpus packages/whisker/corpus --baseline <file> --update
```

`whisker bench` is the measurement command for the same `<pid>.gt.md` files. It prints a leaderboard. A mean overall drop of more than `0.03` against a committed baseline fails that comparison. Bench measures resemblance. It does not measure comprehension.

### Comprehension

```text
whisker facts --corpus packages/whisker/corpus
```

This gates `<pid>.facts.jsonl` against the markdown. Only facts marked `"checked": "verified"` count. The committed corpus reports clean over 5 papers, 37 verified facts gated, 0 vacuous. A facts file with zero verified facts fails closed. In the hermetic corpus check, a facts file without a matching `<pid>.expected.md` is skipped, and a corpus with no such pairs fails, so an empty corpus cannot look green.

This lane is the one that catches a scrambled table or a dropped exponent while the fidelity scores still look fine. While you are still authoring, `--strict` gates draft facts too. The tooling writes scaffolds with `whisker corpus draft`. It never writes `verified` itself. You set that after you locate the needle in the source PDF or HTML.

## How a verdict is decided

A paper becomes `not-llm-readable` in exactly two situations. A structural gate failed, or unigram coverage is below `0.85`. The structural gates, in order, are `non_empty`, `front_matter_valid`, `heading_monotone`, `no_empty_code`, `no_empty_table`, and `no_toc_leak`. Any one failure is a hard fail. Missing words fail the paper. Reordering alone does not. Soft flags do not. Oracle disagreement does not. The advisory lane does not.

A paper that survived those two checks becomes `review` on a soft signal. Unigram coverage from `0.85` up to, but not including, `0.95` is the soft band. Unigram drift above `0.10` is a soft flag. So is a tomd QA score below `70`. So is a block of misaligned regions. Oracle text agreement (`ref_nid`) below `0.85` raises review and stays out of the hard flags. Reading-order disagreement, punctuation-token loss, and a fence boundary that disagrees with a monospaced run of three or more source lines are soft flags of the same kind.

A paper passes when no gate fired. Unigram coverage at or above `0.95` passes the content check. When the only soft flags are misaligned regions and unigram coverage is at least `0.95`, the paper still passes, and the flag stays visible as `(benign)`. Below that floor, the same region flags stay a review.

Exit codes are `0` ok, `1` error, `3` review, and `5` fail. A `not-llm-readable` verdict is considered before a review verdict, so one hard fail exits `5` even if other papers are only at review. A run that scores zero papers exits `1`. Unconverted or source-less papers are skipped with a warning. A paper that crashes is logged and counted, and the rest of the batch continues.

Choose the lowest verdict that still exits `0`:

```text
whisker --gate pass P3100R6
```

That command exits non-zero when `P3100R6` is only at review. `--gate review` is the default: `pass` and `review` exit `0`, and `not-llm-readable` exits `5`. `--gate pass` also rejects `review`, which exits `3`. `--gate not-llm-readable` accepts every verdict and exits `0`. `--all` together with paper ids is a parser error.

## After you change the converter

Work in this order. `whisker delta`, the deterministic comparison, is the command whose exit code reports a regression. `whisker delta --llm` never does.

Reconvert. `convert` skips papers that already have markdown, so force it:

```text
paperflow convert --force <pids>
```

Rescore the fleet. This writes a new `report.json` and copies the previous one to `report.prev.json` first:

```text
whisker --all
```

Compare the two deterministic reports. Sections are regressed, improved, new, gone, and unchanged. A verdict that crosses a boundary sorts ahead of same-verdict noise. A metric wiggle at or below `0.01` is ignored:

```text
whisker delta
```

Exit `0` means nothing regressed. Exit `3` means something did. Exit `1` means the current report or the baseline is missing, including the first run, which has no previous snapshot yet. That is an error, not a clean fleet. Pass `--baseline <path>` to compare against a saved report instead of `report.prev.json`.

Take a warm advisory pass. With no paper ids, unchanged papers are skipped on fingerprint:

```text
whisker-tapetum-llm
```

Compare the advisory aggregate. This reads the merged report against its previous snapshot and does not gate the build. A successful compare exits `0`. A missing merged report exits `1`:

```text
whisker delta --llm
```

## The advisory lane

Install the extra once, when the menu or the import says it is missing:

```text
uv sync --extra tapetum-llm
```

The lane can lower a merged pass to review whenever its own verdict is anything other than pass. A grounded advisory pass can clear a deterministic review that rests only on soft flags. When oracle text agreement is present, that clear requires it to be at least `0.10`. With the oracle off, the same clear can still happen. It cannot clear a hard fail, and an ideal soft flag blocks the clear. The deterministic sidecar stays as the scoring run wrote it, and `whisker --gate` does not read the merge.

Two table signatures sit in this lane, not in the deterministic gate. `row_loss` is `not-llm-readable`: a PDF grid whose rows became headings or prose, two source rows merged into one pipe row, or a repeated continuation-page header emitted as a data row. An empty cell that only continues a rowspan is not row loss. A raw HTML table in markdown that came from a PDF is at least a review. The same HTML table stays allowed when the source itself is HTML.

A rerun skips work it can prove is unchanged. A full-corpus invocation, no paper ids and no `--review-all`, turns that skip on unless you force it. The fingerprint covers the source, the markdown, the prompts, the schemas, the model config, the ideal, and the lane version. Named paper ids stay cold unless you add `--incremental`. An error tombstone from an earlier run is skipped on that path. `--retry-errors` judges those tombstones again. Failures from the current run are retried on their own, in up to two waves, before the process exits.

Force a full re-judgment even when fingerprints match. This applies to a full-corpus run. It is ignored when you name paper ids or pass `--review-all`:

```text
whisker-tapetum-llm --force
```

Preview the skip list. This prints one line per paper, `run`, `skip (fingerprint match)`, `skip (superset: MODE)`, or `skip (tombstone)`, then exits `0`. It does not probe the model, does not call the model, and does not write a sidecar or a merged report:

```text
whisker-tapetum-llm --would-skip
```

Rebuild the merged report from sidecars already on disk, for example after `whisker --all`, with no model call. If those sidecars are newer than the aggregate, the next delta warns you to run this first:

```text
whisker-tapetum-llm --fuse-only
```

An advisory verdict of pass, review, or fail exits `0`, and so does an empty selection. An operational error exits `1`, and only after the remaining papers and the retry waves have finished. `--concurrency` defaults to `16`. `--concurrency 1` runs the papers strictly one at a time. Results are still stored in input order. The fast-slot service is checked with a `GET /health` probe before the batch. If it is unreachable, the run stops with an error. `--would-skip` does not make that probe.

Judge risky papers from the deterministic sidecars instead of the whole fleet, and write the side-by-side file `whisker/llm/tapetum-inspect.md`:

```text
whisker-tapetum-llm --review-all --inspect
```

The blind readback is a different check. It asks a self-hosted model the questions derived from verified facts, and it answers whether those facts are recoverable. It does not judge the conversion, and it is not part of CI:

```text
whisker-readback --corpus packages/whisker/corpus
```

`--service` defaults to `alliance-pod`. Each paper gets `<pid>.readback.md`. In clean mode the process exits `0` only when every check passes, and exits `5` when any check fails. `--corrupt` scrambles the markdown first and inverts that: exit `0` when at least one check fails, and exit `5` when every check still passes. `--corrupt-banner` stays off unless you set it, and it is ignored without `--corrupt`. A missing corpus, workspace, service, API key, or set of verified facts exits `1` before any comprehension verdict.

## Contracts, comparisons, and the survey

Check a converted markdown file against the table-readability contract. The default profile is `deepseek-v4`, and the default construct is tables. The check evaluates the candidate only. It does not certify a model:

```text
whisker llm-readability check FILE
```

Exit `0` is ok, including a vacuous report. Exit `3` is review or incomplete. Exit `5` is fail (`not-llm-readable`). Exit `1` is an operational or contract error. `--json` adds `model_certified: false`. The same verb prints the contract with `rules`, lists profiles with `profiles`, and switches to code fences with `--construct codeblocks`. Rule R14 fails the check when a PDF source arrives as a raw HTML table, or when HTML entities stand in for code inside a table.

Compare this scoring run with the previous one:

```text
whisker delta
```

The command reads `report.json` against `report.prev.json`. Exit `0` is clean, exit `3` is a regression, and exit `1` means a report is missing. `--json` prints one JSON object and nothing else. Add `--llm` for the advisory aggregate. That view exits `0` on a successful compare and never supplies the regression exit code.

Run one competitor survey against the frozen benchmark corpus. `NAME` is a registered competitor:

```text
whisker survey run NAME
```

The report lands under `packages/whisker/benchmark/reports/YYYY-MM/` as `survey-<name>.json` and a matching markdown file, unless you pass `--out DIR`. Each converter gets a stability result, fidelity scores (nid, teds, mhs, overall, content recall), and a comprehension verdict. A limitations paragraph on that report allows claims only about these five papers and these structures. It rules out general superiority, a population-wide error rate, and a general claim of whisker reliability. `whisker survey status` exits `2` when a competitor is due, which is 30 whole days since the last success or a newer upstream version, and exits `0` otherwise. `whisker survey install NAME` builds the runtime under `%LOCALAPPDATA%/whisker/survey/<name>/<version>/`. The run repairs a corrupt runtime once by itself. `--refresh-runtime` forces a full rebuild. If integrity still fails after that one repair, the command exits `1` and points you at `--refresh-runtime`.

The other verbs group by the job:

Score a file with no paperstore, or check facts on that file. `whisker score-file --md FILE` runs the structural gates. Add `--ref FILE` for nid, teds, mhs, and content recall, or `--source FILE` for coverage against a PDF or HTML. `whisker check-facts --md FILE --facts FILE` checks one facts file. A missing required phrase is `not-llm-readable` and exits `5`. A missing markdown file exits `1`, which is an operational error, separate from a failed fact. Add `--anchors FILE` for phrase tripwires. `--json` on `score-file` feeds tomd's whisker metrics panel. `--json` on `check-facts` feeds tomd's comprehension panel.

Fit the two coverage edges from labeled rows that already carry unigram coverage. `whisker calibrate --labels FILE` uses the `calibration` split to choose the threshold and the `holdout` split to report TPR, FPR, and precision. The default ceilings are `0.05` on the fail edge and `0.10` on the review edge. Override them with `--fail-target-fpr` and `--review-target-fpr`. The command writes an artifact, including to `--out FILE`. It does not promote the live constants.

Maintain hand-blessed ideals. `whisker qa` takes `add`, `generate`, `render`, `score`, `bless`, `issue`, `rebless`, `fact`, or `anchor`. `--golden-dir` defaults to the shared tomd fixtures, `packages/tomd/tests/fixtures/golden`, which is where `ideals/` and `baselines.json` live. `rebless` ratchets baselines upward and refuses a lower axis unless you pass `--force`.

Diff two markdown files block by block. This entry point is not the `whisker` console script:

```text
python -m whisker.det.compare.cli run <left.md> <right.md>
```

It prints `Aligned N blocks: E equal, C changed`. `--html out.html` writes a side-by-side report. `--json` writes provenance: both paths, SHA-256 digests, labels, and the pair counts.

On a terminal, `whisker` with no arguments opens the menu. Any argument, or a stdout that is not a terminal, goes straight to scoring.

## Where the files go

Deterministic scoring writes under `$WG21_DATA_DIR/whisker/det/`. Each paper gets `<pid>.whisker.json`. The run also writes `report.json` and `report.md`. Before `report.json` is replaced, the previous file is copied to `report.prev.json`. `whisker delta` reads that pair. `--report-dir` moves this whole set. `--no-write` writes none of it. The menu's report view reads `$WG21_DATA_DIR/whisker/det/report.md`.

The advisory lane writes beside that directory, in `whisker/llm/`. A full run produces `report-merged.md` and `report-merged.json`, and keeps the previous aggregate as `report-merged.prev.json`. `whisker delta --llm` reads that pair. Rows carried forward from an earlier run are marked `replayed`. `--inspect` also writes `tapetum-inspect.md` in that directory. `--fuse-only` rebuilds the merged pair from the sidecars already on disk and does not call a model. `--would-skip` writes nothing.

Readback reports are separate. With `--out`, each paper is `<pid>.readback.md`, or `<pid>.readback-corrupt.md` when corrupt mode is on. A recorded live run stored its reports at `data/whisker/readback/<pid>.readback.md`.

## What a pass does not prove

The content gate counts words. Unigram coverage stays green when `->` becomes `.`, when a semicolon becomes a comma, and when two headings swap places without losing a word. `P0876R23` dropping `pf1->resume();` down to `pf1.resume();` is that case: the normalized text of `p->next` and `p.next` matches, and the deterministic score does not see the operator. Punctuation-preserving recall can raise a soft flag when it lags unigram coverage by more than `0.02`. That flag reviews the paper. It does not fail it. The footer sentence is the contract: a pass means no gate fired, not that the conversion is correct.

The stability compare is blind to a smaller edit. It turns CRLF and CR into LF, strips trailing whitespace on each line, and keeps a single trailing newline. A golden diff will not show those changes. Bless with `--update` only after a policy change you intend to accept. The snapshot version moves with the normalizer so a policy change becomes a review, rather than a silent mass of diffs.

The lane that sees operator-level corruption is comprehension, and only after a person has written the check. A verified fact on the raw surface keeps case, punctuation, and operators. That is what fails `pf1->resume();` rewritten as `pf1.resume();`, a semicolon rewritten as a comma, two headings swapped, a scrambled table, or a dropped exponent, while coverage and fidelity still look fine. `whisker corpus draft` writes `"checked": "draft"`. You set `verified` after you find the needle in the source. Until you do, the fact is advisory and this gate does not use it.

The coverage edges in force are `0.85` for a hard fail and `0.95` for review. They are provisional: adopted from published clean-conversion recall norms, not fitted on this corpus. `whisker calibrate` can fit an edge from labeled rows and record why a thin edge was not fit. It writes an artifact. It does not change the edges the scorer uses.
