# Bug: Abschnittsnummerierung aus Quelle geht in Markdown verloren

## Beobachtung

In den WG21-Quellen (HTML aus Bikeshed, teils PDF) sind Ueberschriften oft **nummeriert** oder der Zaehler steht **strukturell getrennt** vom Titel (eigener `span`, eigene Typo). Im konvertierten Markdown erscheint die Ueberschrift haeufig **ohne** diese Nummer, nur als reiner Titel.

Das betrifft typische Abschnitte wie **Introduction** oder **Motivation**: im Quell-HTML steht z. B. `1. Introduction` sichtbar, im Markdown steht `## Introduction`.

## Was daran "falsch" laeuft

1. **Semantischer Verlust:** Die Ueberschrift in der Ausgabe ist nicht mehr dieselbe Zeichenkette wie in der normativen bzw. veroeffentlichten Quelle. Verweise wie "siehe Abschnitt 2" oder das Inhaltsverzeichnis der PDF sind nicht mehr trivial mit dem Markdown abgleichbar.

2. **Struktur wird verworfen, die in der Quelle existiert:** Beim HTML ist die Nummer **kein** bloesser Praefix im gleichen Knoten wie der Titel, sondern oft ein separates Element:

   ```html
   <h2 class="heading settled" data-level="1" id="introduction">
     <span class="secno">1. </span><span class="content">Introduction</span>
   </h2>
   ```

   Wenn die Pipeline nur den "sichtbaren" Titeltext oder den `content`-Span nach Markdown abbildet, fehlt `secno`. Optional sind **unterschiedliche Schriftgroessen** fuer Zahl und Titel moeglich (CSS), die in Plain-Markdown ohnehin nicht abgebildet werden, aber die **Zahl selbst** sollte aus Sicht der Quelltreue erhalten bleiben, wenn sie strukturell vorliegt.

3. **PDF:** In manchen PDFs erscheint im linearen Textextrakt kein `1. Introduction`, obwohl auf der Seite eine klare Kapitelfuehrung (TOC vs. Fließueberschrift) mit **unterschiedlichen Fontgroessen** existiert (z. B. kleinere TOC-Zeilen vs. groessere Body-Ueberschrift). Die reine Textkette ist dann irrefuehrend, die visuelle Struktur steckt in Layout/Spans.

4. **Inkonsistenz innerhalb der Pipeline:** Ein Teil der Papers hat im Markdown bereits Praefixe wie `## 2. Introduction` (Beispiel P3856R*), andere mit gleichem HTML-Muster haben nur `## Introduction`. Das deutet auf **ungleiche Heuristiken** oder unterschiedliche Quellzweige hin und erschwert Batch-Verarbeitung und Vergleiche.

## Konkrete Beispiele (data/paperstore)

**HTML + Markdown (klarster Fall):** Markdown `## Introduction` bzw. `## Motivation`, HTML enthalten `<span class="secno">…</span>` mit Nummer am gleichen `h2`. Auszug gut reproduzierbar, z. B.:

- `p3769r1.md` / `p3769r1.html` (H2: `1. Introduction`)
- `p3873r0.md` / `p3873r0.html`
- `p3904r1.md` / `p3904r1.html` (Introduction und Motivation)
- `p3965r0.md` / `p3965r0.html`
- `p3973r0.md` / `p3973r0.html`
- `p4006r0.md` / `p4006r0.html`
- `p4027r0.md` / `p4027r0.html`
- `p4197r0.md` / `p4197r0.html` (H2: `2. Introduction`)

Im selben Ordner gibt es **viele** weitere HTML-Paare dieses Musters (grobe Groessenordnung: mehr als drei dutzend, wenn man alle `.md` mit exakt `## Introduction` / `## Motivation` gegen `.html` mit `secno` abgleicht).

**Nur PDF (ohne HTML im store):** gleiches Markdown-Muster, aber Nummer nicht zuverlaessig in `get_text("text")`, z. B. `p3427r3.md` / `p3427r3.pdf`, `p3625r1.md` / `p3625r1.pdf` (Ueberpruefung der Ueberschriften-Groessen sinnvoll ueber `get_text("dict")` / Spans).

## Abgrenzung (HTML vs. PDF)

- **Hauptfall fuer genau diesen Bug (Nummer in der Quelle, weg im Markdown):** **Bikeshed-HTML** mit getrenntem `span.secno` und `span.content`. Fix liegt in **HTML-Pipeline/Emit**, nicht in PDF-Textregex als erstem Schritt.
- **PDF im lokalen `data/paperstore`:** Wo **`1. Introduction`** (o. a.) **wirklich im PDF-Text** vorkommt, ist es im Markdown oft **bereits** als `## 1. Introduction` abgebildet. Wo das Markdown nur `## Introduction` hat, fehlt dieselbe Zeichenkette **haeufig auch im PDF-Text** (Autoren-PDF), waehrend das **HTML** die Nummer haette. Das ist dann **kein Spiegelbild des secno-Bugs**, sondern fehlende oder anders kodierte Semantik im PDF.
- **Folge:** PDF-Heuristiken (TOC, Schriftgroesse) sind fuer **andere** Luecken sinnvoll, duerfen aber nicht mit dem **secno-Verlust** verwechselt werden.

## Erwartetes Verhalten

- Wenn die Quelle eine **explizite Abschnittsnummer** fuer die Ueberschrift liefert (HTML: `secno`, PDF: zuverlaessig erkennbar aus Struktur oder TOC+Body-Mapping), soll die Markdown-Ueberschrift diese Information enthalten, z. B. `## 1. Introduction`, konsistent zum restlichen Korpus.
- Mindestziel: **Konsistente Regel** (immer Praefix, wenn in Quelle vorhanden), dokumentiert in `PDF_ARCH.md` / `HTML_ARCH.md` und abgesichert durch Tests mit Golden-Fixtures.

## Moegliche Richtungen zur Behebung

- HTML: beim Rendern von `h2`/`h3` den Text von `span.secno` mit dem `span.content` verketten, bevor die Markdown-Ueberschrift gebildet wird (oder Nummer als Metadatum mitschleifen und in emit einfuegen).
- PDF: Heuristik fuer Ueberschriftenzeilen anhand Fontgroesse/-gewicht und optional TOC-Alignment, statt nur Fliesstext.

## Betroffene Bereiche (vermutlich)

- `packages/tomd/src/tomd/lib/html/` (Rendering aus HTML-Struktur)
- `packages/tomd/src/tomd/lib/pdf/` (Ueberschriften-Erkennung)
- `packages/tomd/src/tomd/HTML_ARCH.md`, `PDF_ARCH.md` (Zielverhalten festhalten)
