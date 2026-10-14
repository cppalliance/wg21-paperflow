# SYNTHESIS - Haben wir mit "deterministische Gates entscheiden, LLM beraet" den falschen Weg eingeschlagen?

**Datum:** 2026-07-16. **Methode:** 3-stufiger Persona-Schwarm (6 Composer-Scouts + 5
Web-Foragers -> 25 Composer-Personas -> 5 Sonnet-5-Meta-Reviewer mit Live-Code- und
Laufzeit-Re-Verifikation). Evidenzbasis: 31 lokale Referenz-Klone, 25 Web-Quellen
(2024-2026), unser eigener whisker-Code, 381 Produktions-Sidecars, die 2026-07-16
PR-Replay-Daten. Alle Reports unter `research/llm-qa-integration/`.

---

## Die Antwort auf die Kursfrage

**Nein. Die Richtung ist nicht falsch - sie ist die Ecosystem-Norm, und unter unseren
Produkt-Constraints sogar zwingend. Aber der Zweifel des Operators trifft etwas Reales:
nicht die Architektur, sondern die GROESSE und FORM der Advisory-Lane.**

Drei Evidenz-Schichten, jede unabhaengig re-verifiziert:

1. **0 von 31 Referenz-Repos lassen ein LLM-Qualitaetssignal mechanisch ueber
   accept/reject/CI entscheiden.** Der Satz hat die schaerfste Pruefung ueberstanden:
   P15 hat eine praezise Gating-Taxonomie gebaut (Signal -> Effekt -> Blast-Radius) und
   die 6 tragenden Anker im Live-Klon nachgelesen; P25 und Meta-Reviewer C haben die
   sekundaer belegten Claims direkt in den Klonen re-verifiziert (Ergebnis: Substanz
   haelt, nur Zitat-Zeilen waren gedriftet, alle korrigiert in `00-baseline.md`). Die
   "LLM-integrierten" Repos, die den Zweifel ausgeloest haben, nutzen LLMs als
   KONVERTIERUNGS-Engine oder fuer beschraenkte mechanische Retries (marker
   `llm_table.py`: score<4 -> Tabellen-Rewrite-Retry, Dokument shippt trotzdem) - nie
   als Richter ueber das Ergebnis.
2. **Die Web-Literatur 2024-2026 erklaert warum:** LLM-Judges sind positions-biased,
   selbst-bevorzugend, systematisch overconfident; Judge-Gates in CI produzieren flaky
   Builds (bis ~50% per-item-Disagreement bei Default-Temperatur). olmOCR-Bench und
   ParseBench sagen es explizit: deterministische Unit-Tests STATT LLM-as-judge
   (`05-web.md` Q1/Q2/Q5).
3. **Unsere eigenen frischen Zahlen:** Der 2026-07-16 PR-Replay ging 4/9 -> 5/9 -> 8/9
   Human-Agreement, und ALLE 4 neuen Hard-Fails kamen aus dem deterministischen Gate
   (~40 LOC Regex), waehrend das LLM in zwei Prompt-Generationen dieselben TOC-Leaks
   still uebersehen hatte. Meta-Reviewer B hat auf 381 echten Sidecars nachgemessen:
   die Confidence des LLM ist dekorativ (96/96 `llm_clear_soft_review`-Firings bei
   >= 0.95; der 0.50-Floor hat nie gebunden; PR #282 wurde mit Confidence 1.00 FALSCH
   freigegeben). P23s gemessene Flip-Rate (>= 25% der Borderline-Papers bei identischen
   Reruns) macht jedes exit-code-bindende LLM-Signal heute zu einem Wuerfelwurf.

Dazu kommt der Sovereignty-Constraint (P22, Meta-C): die Referenz-Repos fahren ihre
LLM-Lanes auf Gemini/Claude. Wir duerfen das fuer verteidigbare Findings nicht, und
Judge-Qualitaets-Paritaet unseres self-hosted Stacks ist unbewiesen. Det-first ist fuer
uns nicht nur klug, sondern notwendig.

## Der berechtigte Kern des Zweifels (steelmanned, nicht weggewischt)

Meta-Reviewer C formuliert es am schaerfsten: Die ehrliche "falscher Weg"-Variante ist
nicht "LLM sollte gaten", sondern **"wir haben moeglicherweise 4.751 LOC
narrativ-generierende Advisory-Werkzeuge gebaut, wo dieselben Stunden in
deterministisches Fact-Mining mehr verteidigbare Catches produziert haetten."**

- Einziger querbestaetigt-einzigartiger LLM-Catch im Inventar: PR #293s 31 gedroppte
  `constexpr` (code-Achse, conf 0.95). Auf der frischesten Kohorte: 0/4 unique Catches.
- MC2 (TOC-Leak) wurde von Regex geschlossen, nicht vom LLM.
- Advisory-Lauf ist 25-177x langsamer als der Det-Sweep (P21, Arithmetik von Meta-C
  nachgerechnet); Judge-Mitigations aus der Literatur wuerden das nochmal x6
  multiplizieren.
- Die Kaskade war auf dem Confidence-Band tot (0/198); die VLM-Lane (788 LOC, von
  Meta-D nachgezaehlt) ist komplett unverdrahtet.

Das ist KEIN Beweis, dass die Lane wertlos ist - sie lokalisiert und erklaert (grounded
Quotes, Achsen-Findings), was das Gate nur binaer meldet, und sie ist die einzige
Instanz gegen token-erhaltende semantische Korruption (Tabellen-Zellen-Swap,
Abschnitts-Permutation), fuer die das Gate strukturell blind ist. Aber die
Beweislast fuer WEITEREN Ausbau liegt jetzt bei einem gelabelten Holdout-Experiment
(>= 30 Papers, von P11/P13/P21/P22 unabhaengig gefordert), nicht bei mehr Features.

## Was der Schwarm konkret gefunden hat (verifiziert, dedupliziert)

### Bestaetigt und architektur-relevant

| # | Befund | Quelle |
|---|---|---|
| 1 | `whisker --gate` ist beweisbar fusion-frei: kein Import, kein Pfad, auf dem LLM-Output den Exit-Code aendern kann. Die Grenzbehauptung der Architektur haelt unter Druck. | Opus-E |
| 2 | `no_toc_leak` ist gleichzeitig unter-inklusiv (Dot-Leader `....... 3`, roemische Ziffern, Klammern, umformulierte Eintraege, `Inhaltsverzeichnis`, tabellenfoermige TOCs passieren) und ueber-inklusiv (legitimes `## Table of Contents`, `## C++ 26`/`## C++` hard-failen). Beides live reproduziert. | Opus-A |
| 3 | Token-erhaltende Korruption (Reorder, Zellen-Swap, Math-Variablen-Swap) ist der strukturelle Blind-Spot der Fleet-Gates, und Fusion kann sie selbst bei LLM-Catch nur auf `review` heben, nie `fail` (by design). Geteilt mit dem gesamten Ecosystem, nicht whisker-spezifisch. | Opus-A |
| 4 | `score-baseline.json` pinnt bekannt-kaputte Gates als Soll-Zustand (4 Goldens mit `false`-Gates), `WHISKER_PIN_UPDATE=1` hat keinen CI-Guard. Der Mechanismus, durch den TOC-Leaks in geweihten Goldens ueberleben konnten. | Opus-A |
| 5 | LLM-Confidence ist anti-kalibriert und dekorativ: 0/381 Sidecars unter dem 0.50-Floor, alle 96 clear-Firings bei >= 0.95, PR #282 falsch-clear bei 1.00. Ordinale Verdicts + Grounding sind die einzige sichere Nutzflaeche. | Opus-B |
| 6 | LLM-Verdicts sind auf unserem Pod nicht CI-stabil: >= 25% Flip-Rate (untere Schranke) bei identischen Reruns; Achsen-Findings speisen denselben nicht-batch-invarianten Output wie das Verdict. CI-Binding ist tot, bis `VLLM_BATCH_INVARIANT_LEVEL` gemessen <= 1% liefert. | Opus-B |
| 7 | Die Blessing-Pipeline hatte keinen `whisker --gate`-Hook auf Golden-PRs (lokales `bless_stem` hat ihn, CI nicht) - so kamen TOC-Leaks in 4 von 9 PR-Ideals und ein committetes Golden. | Opus-A |

### Bestaetigt, aber Hygiene (Lane-intern, beruehrt die Grenze nicht)

- Stale Sidecar ohne Tombstone bei Rerun-Fehler (`cli.py:865-873`) - Opus-E.
- Unwrapped HTML-Outline (`adjudicate.py:400-419`) und Readback-Prompt
  (`readback.py:273-317`) ausserhalb des `inject_untrusted`-Envelopes; Blast-Radius
  durch Fusion-Asymmetrie gedeckelt - Opus-E.
- Substring-Match-Antipattern lebt noch im deterministischen Scorer selbst
  (`score.py:234-238` und `adjudicate.py:128-137`, Region-Matcher) - dieselbe
  Bug-Klasse wie der 2026-07-16-Heading-Fix, nur halb geschlossen - Opus-E.
- `--gate review` exitet 0 fuer review: dokumentiertes Design, Onboarding-Risiko,
  kein Bug - Opus-E.
- 5 stale Doku-Stellen (Kaskaden-Trigger, "serial und deterministisch",
  Testzahlen) - exakte Fix-Liste in Opus-E.

### Widerlegt / korrigiert

- "Nur Tab-getrennte Ziffern triggern den Pairwise-Matcher" - falsch, `\s+` matcht
  auch Spaces (Opus-A).
- F1 (missing_region-Upgrade-Bug) ist im aktuellen Code bereits gefixt
  (`FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION`) - der aeltere Findings-Doc ist ueberholt
  (Opus-B).
- VLM-Lane-LOC: 788, nicht ~637 (Opus-D). 7 Baseline-Anker gedriftet, alle korrigiert
  (Opus-C).
- P16s `extract_vector`-Retry-Trigger ist kontraproduktiv (kann Body-Text droppen statt
  retten); `ml_tables` haengt an undeklariertem `docling` (Opus-D).

## Handlungsliste (nach Kosten, konsolidiert aus A-E)

**Sofort, nahezu kostenlos:**
1. Confidence im Report als "self-reported, uncalibrated" labeln oder Dezimal-Anzeige
   streichen (Opus-B #1).
2. Die 5 stale Doku-Zeilen fixen (Opus-E Liste).
3. Pinning-Meta-Test: neue/geaenderte Baseline-Eintraege mit `false`-Gates brauchen
   explizite Annotation; `WHISKER_PIN_UPDATE=1` bei `CI=true` blocken (Opus-A #1,
   pandoc-Disziplin).

**Billig, hoher Hebel:**
4. P18-Adopt: fuzzy-only-Demotion in `adjudicate.py` (~5-10 LOC, Daten schon
   berechnet) - bester Value/Cost im ganzen Schwarm (Opus-D #1).
5. `llm_escalate_major` / per-page confirmed-missing als LAUTE Advisory-Zeile in
   report/inspect promoten - nicht als Gate (Opus-B #2).
6. Tombstone-Write auf dem Rerun-Fehlerpfad (Opus-E #2).
7. Region-Matcher auf Prefix/`gates[].name` umstellen, beide Stellen (Opus-E #3).
8. `whisker --gate fail` als CI-Hook auf `ideals/*.md` in Golden-PRs (Opus-A/#19) -
   der fehlende Blessing-Guard.
9. Grader-Disagreement-Rate als stehende Metrik (fixe 20-PID-Slice, 2x pro
   Lane-Release) (Opus-B #3).
10. Divergenz-KPI loggen: LLM-Verdict != Det-Verdict + spaeter human-bestaetigt?
    Macht "unique catch inventory" zur laufenden Zahl (Opus-C #3).

**Mittel:**
11. TOC-Gate-Design-Iteration: False-Fail-Seite entschaerfen (WG21-Exemption oder
    Soft-Flag-Demotion) OHNE die False-Pass-Seite wieder zu oeffnen; fehlende
    Test-Fixtures (lokalisiert, mehrzeilig, Full-Phrase) dazu (Opus-A #2/#5).
12. `auto_baseline_checks` + uni-cov-Gap als deterministische Soft-Flags verdrahten
    (Opus-A #3) - reduziert die Abhaengigkeit davon, dass die LLM-Lane ueberhaupt laeuft.
13. P24-Adopt: `tomd:page-failed`-Marker + Hard-Gate, inkl. des von Opus-D gefundenen
    both-paths-empty-Falls (nougat-Muster, rein deterministisch).
14. VLM-Lane (788 LOC) loeschen oder explizit quarantaenisieren; getrennt von der
    Prompt-Authority-Konsolidierung halten (Opus-D #3).
15. Naechste Tapetum-Iteration Richtung Fact-Mining biasen: LLM schlaegt mechanische
    Checks vor, Mensch verifiziert Sample, Check wird permanente Gate-Regel - das
    MC2/olmOCR-Muster (Opus-C #4).

**Gross, ist das eigentliche Entscheidungs-Gate:**
16. Gelabeltes Holdout-Experiment (>= 30 Papers): faengt die Advisory-Lane > 15% der
    Defekte, die det+facts verpassen, ohne False-Pass-Anstieg? Erst dessen Ergebnis
    entscheidet ueber weiteren Lane-Ausbau vs. Umschichtung (Opus-C #6).
17. Flip-Rate unter `VLLM_BATCH_INVARIANT_LEVEL` messen (P23s Falsifier); nur bei
    <= 1% ist irgendein CI-Binding je wieder diskutabel (Opus-B #5).

**Nicht tun:**
- LLM-Signal (self-hosted oder cloud) zum mechanischen Gate machen - 0/31 Repos,
  Literatur, Flip-Messung und Sovereignty sagen alle dasselbe.
- `extract_vector` als Retry-Trigger; Temperatur-Eskalation oder stiller
  Engine-Downgrade bei Retry (invertiert unser Fidelity-Invariant).
- langextracts LCS-0.75-Tier ins Grounding uebernehmen (akzeptiert gapped-wrong-spans
  by design).

## Prozess-Lektion dieser Recherche

`packages/whisker/research/.gitignore` blendet `repos/` aus; gitignore-respektierende
Suchwerkzeuge melden die Klone als leer. Drei Personas fielen darauf zurueck auf
Sekundaerquellen. Root-Cause dokumentiert in `00-baseline.md` §6; Konsequenz fuer alle
kuenftigen Repo-Recherchen: `rg --no-ignore --no-ignore-vcs` oder direkte Pfade.
Zusatzfund von Meta-C: PowerShell `Get-ChildItem -Recurse` liefert auf verschachtelten
`.git`-Klonen (opendataloader-bench-tmp) faelschlich leer; `cmd /c dir /b` nicht.

## Verdikt-Verteilung

25 Personas: 24x usable-with-conditions, 1x usable, 0x garbage. 5 Meta-Reviewer:
5x usable-with-conditions. Kein einziger Report - einschliesslich des beauftragten
Steelman-LLM-First - kam zu dem Schluss, dass die Gate-vs-Advise-Entscheidung falsch
war. Der staerkste ueberlebende Einwand ist die ROI-Frage an die Lane-Groesse, und die
ist mit Aktion #16 falsifizierbar gemacht.
