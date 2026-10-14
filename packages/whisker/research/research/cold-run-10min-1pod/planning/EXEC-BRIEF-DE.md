# Executive Brief — Cold-Run ≤10 Min (1 MoE-Pod)

**Datum:** 2026-07-24 · **Zielgruppe:** Ops, Engineering, Entscheidungsträger  
**Produkt:** Whisker `tapetum-llm`, Bare Full-Fleet Cold (381 Papers, ~2284 LLM-Calls)

---

## Lage

Gemessen: **~48–50 Min** Cold-Run auf `alliance-pod` (DeepSeek-V4-Pro, max. 16 parallele Sequenzen). Ziel: **≤10 Min**, bei gleicher Qualitätsstabilität (gleiche fused Verdicts).

Zweites V4-Pro-Pod ist **verboten** (Budget/Authority). Parallelität auf dem MoE-Pod bleibt bei **16** (32 verschlechtert die Wandzeit).

Mit dem bereits im Tree liegenden v11-Short-Circuit sind realistisch **~21–25 Min** erreichbar — noch weit über 10 Min. **MoE allein kann 10 Min bei Qualität physikalisch nicht treffen** (Frontend allein schon ~948 s).

---

## Blocker (kritisch)

Alle densen Alliance-Endpoints in `SERVICES.toml` liefern **HTTP 404**:

| Endpoint | Status |
|----------|--------|
| `alliance-pod` (MoE) | **UP** |
| `h200-qwen3-32b` (primär nötig) | **404** |
| `b300-qwen36-27b`, `b200x2-gemma4`, `b200-r1` | **404** |

Ohne laufendes Dense-Pod ist der einzige ≤10-Min-Pfad **infra-blockiert**. Policy-Freigabe reicht nicht — der Pod muss antworten.

---

## Optionen

| | **A — MoE-only** | **B — Heterogen (Dense)** | **C — SLA reset** |
|---|---|---|---|
| **Versprechen** | Qualitätssstack shippen; **kein** ≤10-Min-Claim | ≤10 Min via Parallel-Lauf MoE+Dense | Programm 10 Min beenden |
| **Realistische Wand** | ~15–20 Min (ehrlich); MODERATE ~23–25 Min | ~511 s möglich, wenn Dense + Scoping + Parity | ~15–20 Min veröffentlicht |
| **Infra heute** | `alliance-pod` UP — **shippable** | Dense alle 404 — **blocked** | Keine Dense-Abhängigkeit |
| **≤600 s?** | **Nein** | **Vielleicht** (Design; heute tot) | Ziel verschoben |

**Empfehlung bei unklarem Dense-Restart:** A bauen + C-Sprache (ehrliches SLA). B nur mit datiertem Ops-Commit.

---

## Was Alliance Ops tun muss

**Ask:** Endpoint **`h200-qwen3-32b`** neu starten, bis `GET /v1/models` → **HTTP 200**.

- **Warum:** ~1500–1800 Unit-/Metadata-Calls vom geteilten MoE-Pod abnehmen. Einziges arithmetisches ≤10-Min-Design unter Twin-Verbot.
- **Nicht gefragt:** zweites V4-Pro, MoE `max-num-seqs` erhöhen, Exklusiv-Reservierung von `alliance-pod`.
- **Nicht priorisieren als Unit-Judge:** Gemma-4, R1.
- **Wenn kein Restart:** 10-Min-Programm stoppen; ehrliches SLA **~15–20 Min**.

---

## Was das Code-Team ohne Infra tun kann

Sofort, nur mit `alliance-pod`:

1. Cold auf lokalem v11 neu messen (Wahrheits-Baseline ~21–25 Min).
2. v11 Short-Circuit committen/shippen.
3. Deterministische Metadata (Shadow A/B, HTML-first → Fleet).
4. Verdict-first Schema + Router/Quota (mit Holdout-Gates).
5. Server Tier-1 Flags (MBT, CUDA Graphs, DeepEP) — allein nicht genug für 10 Min.

**Nicht tun:** Twin vorschlagen, S=32, Monolith skippen, Dense-Router gegen tote 404-Proxies shippen.

**Nach Dense-UP (Ops):** Payload-Scoping → Cascade → 381er Qualitätsgate (~0.8–1.2 h Validierung) → erst dann ≤10 Min claimen (instrumentiert ≤620 s + Parity).
