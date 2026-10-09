"""Temp: find error papers and merge quantification."""
import json
import glob
import os

base = r"C:\Users\sabo2\Desktop\cppalliance\data\whisker"
wh_files = [f for f in glob.glob(os.path.join(base, "*.whisker.json")) if ".tapetum." not in f]
tap_files = glob.glob(os.path.join(base, "*.whisker.tapetum.json"))

tap_pids = set()
for tf in tap_files:
    with open(tf, encoding="utf-8") as f:
        t = json.load(f)
    tap_pids.add(t.get("pid", "").upper())

# candidate selection simulation
REVIEW = "review"
PASS = "pass"
FAIL = "fail"
COV_UNIGRAM_GAP_TRIGGER = 0.05  # check actual constant
REGION_BENIGN_UNIGRAM_FLOOR = 0.95

candidates = []
no_tap = []
for wf in wh_files:
    with open(wf, encoding="utf-8") as f:
        w = json.load(f)
    pid = w.get("pid", "")
    verdict = w.get("verdict", "")
    if pid.upper() not in tap_pids:
        no_tap.append(w)
    # classify why no tapetum
    if pid.upper() not in tap_pids:
        candidates.append((pid, verdict, "no_tapetum_sidecar", w.get("soft_flags", []), w.get("hard_flags", [])))

print("whisker count:", len(wh_files))
print("tapetum count:", len(tap_files))
print("no tapetum sidecar:", len(no_tap))

# verdict breakdown of no-tap
from collections import Counter  # noqa: E402
vc = Counter(w.get("verdict") for w in no_tap)
print("no-tap verdicts:", dict(vc))

# baseline says 6 errors from 200 candidates - find review/fail papers in 200-candidate set that lack tapetum
# 200 candidates = 194 adjudicated + 6 errors
# Papers WITH tapetum = 204 (hmm more than 194)

# List no-tap that would be candidates (review non-benign, fail heading-only, pass risk)
def is_benign_region_only(r):
    soft = r.get("soft_flags", [])
    if not soft:
        return False
    region = [f for f in soft if "misaligned region" in f.lower()]
    return len(region) == len(soft) and r.get("unigram_coverage", 0) >= REGION_BENIGN_UNIGRAM_FLOOR

def is_heading_only_fail(r):
    hard = r.get("hard_flags", [])
    if not hard:
        return False
    heading = [f for f in hard if "heading" in f.lower()]
    return len(heading) == len(hard)

def has_pass_risk(r):
    if r.get("lossy_table_count", 0) > 0:
        return True
    if r.get("table_parse_errors", 0) > 0:
        return True
    if r.get("mojibake_count", 0) > 0:
        return True
    uni = r.get("unigram_coverage", 0)
    cov = r.get("coverage", 0)
    if (uni - cov) > COV_UNIGRAM_GAP_TRIGGER:
        return True
    return False

error_candidates = []
for w in no_tap:
    pid = w.get("pid")
    v = w.get("verdict")
    would_select = False
    reason = ""
    if v == PASS and has_pass_risk(w):
        would_select = True
        reason = "pass_risk"
    elif v == REVIEW and not is_benign_region_only(w):
        would_select = True
        reason = "review_non_benign"
    elif v == FAIL and is_heading_only_fail(w):
        would_select = True
        reason = "heading_rescue"
    if would_select:
        error_candidates.append((pid, v, reason, w.get("soft_flags", []), w.get("hard_flags", [])))

print("\nno-tap that WOULD be candidates:", len(error_candidates))
for e in sorted(error_candidates):
    print(f"  {e[0]}: {e[1]} ({e[2]}) hard={e[4]} soft={e[2][:1]}")

# Known error PIDs from baseline
known_errors = ["P2728R11", "P2728R12", "P3568R2", "P3904R1", "P3951R1", "P4233R0"]
print("\nknown error PIDs tapetum status:")
for pid in known_errors:
    tf = os.path.join(base, f"{pid.lower()}.whisker.tapetum.json")
    print(f"  {pid}: {'HAS tapetum' if os.path.exists(tf) else 'NO tapetum'}")

# Merge quantification
tap_rows = []
for tf in tap_files:
    with open(tf, encoding="utf-8") as f:
        t = json.load(f)
    tap_rows.append(t)

def worst_of(wv, tv):
    order = {PASS: 0, REVIEW: 1, FAIL: 2}
    return wv if order[wv] >= order[tv] else tv

def llm_rescue_merge(wv, tv, has_major_fail=False):
    """Asymmetric: tapetum pass clears whisker review; fail ceiling unless whisker fail."""
    if tv == PASS and wv == REVIEW:
        return PASS
    if wv == FAIL:
        return FAIL  # whisker_fail_locked
    if tv == FAIL and not has_major_fail:
        tv_eff = REVIEW
    else:
        tv_eff = tv
    return worst_of(wv, tv_eff)

def tapetum_trust_pass(wv, tv):
    if tv == PASS:
        return PASS
    return wv if wv == FAIL else worst_of(wv, tv)

worst_of_inflated = 0
rescue_clears = 0
fail_locked = 0
heading_stuck_review = 0
unknown_blocks = 0

for t in tap_rows:
    wv = t.get("whisker_verdict")
    tv = t.get("suggested_verdict")
    findings = t.get("axis_findings", [])
    has_major = any(f.get("verdict") == FAIL and f.get("severity") == "major" for f in findings)
    wo = worst_of(wv, tv)
    rm = llm_rescue_merge(wv, tv, has_major)
    if wv == REVIEW and tv == PASS and wo == REVIEW:
        worst_of_inflated += 1
    if wv == REVIEW and tv == PASS and rm == PASS:
        rescue_clears += 1
    if wv == FAIL and tv in (REVIEW, PASS) and rm == FAIL:
        fail_locked += 1
    if wv == FAIL and tv == REVIEW:
        heading_stuck_review += 1

# no-tap papers: merged=unknown
for w in no_tap:
    v = w.get("verdict")
    if v in (PASS, REVIEW):
        unknown_blocks += 1

print("\n--- merge quantification (194 adjudicated + extras) ---")
print(f"worst-of keeps review when tapetum=pass (det=review): {worst_of_inflated}")
print(f"asymmetric rescue clears review->pass: {rescue_clears}")
print(f"whisker_fail_locked blocks fail->review rescue: {fail_locked}")
print(f"fail->review heading rescues (tapetum): {heading_stuck_review}")

# double-count: det soft mentions heading/drift/region AND llm structure finding
double_count = []
for t in tap_rows:
    wf = os.path.join(base, f"{t['pid'].lower()}.whisker.json")
    if not os.path.exists(wf):
        continue
    with open(wf, encoding="utf-8") as f:
        w = json.load(f)
    soft = " ".join(w.get("soft_flags", [])).lower()
    hard = " ".join(w.get("hard_flags", [])).lower()
    struct_findings = [f for f in t.get("axis_findings", []) if f.get("axis") == "structure" and f.get("verdict") != PASS]
    if struct_findings and ("heading" in soft or "heading" in hard or "drift" in soft):
        double_count.append((t["pid"], w.get("verdict"), t.get("suggested_verdict"), w.get("soft_flags"), struct_findings[0]))

print(f"\ndouble-count heading/drift det+llm: {len(double_count)}")
for d in double_count[:12]:
    print(f"  {d[0]}: det={d[1]} tap={d[2]} soft={d[3][:2]} llm={d[4].get('note','')[:60]}")

# chunked papers
chunked = [t for t in tap_rows if "chunked into" in (t.get("primary_concern") or "") or "aggregated over" in (t.get("reasoning") or "")]
print(f"\nchunked papers in tapetum: {len(chunked)}")
for c in chunked:
    print(f"  {c['pid']}: {c.get('whisker_verdict')}->{c.get('suggested_verdict')} concern={c.get('primary_concern','')[:80]}")
