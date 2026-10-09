# C++ Alliance report layout pattern

`LAYOUT-REFERENCE.pdf` in this directory is the design contract. Every PDF this
project generates should look like it. The stylesheet beside it,
`alliance.css`, was derived from that file by measurement rather than by taste.

## How to use it

Never hand-roll a document shell. Go through `whisker.branding`:

```python
from whisker.branding import html_to_pdf, render_branded_html

html = render_branded_html(markdown_text)          # branded HTML, self-contained
Path("out.html").write_text(html, encoding="utf-8")
html_to_pdf(Path("out.html"), Path("out.pdf"))     # headless Chromium
```

For a non-Markdown body, assemble it yourself and wrap it:

```python
from whisker.branding import ReportMeta, wrap_document

meta = ReportMeta(title="...", subtitle="...", fields=(("Corpus", "v2"),))
html = wrap_document(body_html, meta, extra_css=MY_CSS, landscape=True)
```

`whisker.det.compare.render_pdf` is the worked example of the landscape variant.

## What the pattern is

**Masthead.** Title on the left at 16pt semibold, the Alliance shield on the
right at 41pt wide, separated from the body by a 1.5pt rule in `#dfddd8`. The
title is not part of the text flow, which is why `render_branded_html` lifts the
leading `# Heading` and the `**Label:** value` lines beneath it out of the body.

**Type.** 10pt body at 1.75 line height. Headings at 16 / 13 / 11.5 / 9.5pt,
semibold, never coloured. Generous space above a heading, tight below it, so
sections read as grouped rather than evenly spaced.

**Palette.** Brand red `#a81c21` for rules, accents and links. Code red
`#aa3344` for inline code. Body black, with `#333333`, `#4a4a4a` and `#6b6b6b`
for descending emphasis. Panels and table headers in `#f5f4f1`.

**Inline code carries colour, not a box.** The reference sets inline code in
`#aa3344` with no background. Technical prose here is dense with identifiers, and
giving each one a grey rectangle turns a paragraph into a field of boxes.

**Tables.** Horizontal rules only, no vertical borders, header row on the panel
tint, 6 to 7pt cell padding. Columns are separated by whitespace.

**Blockquotes and code blocks.** Panel background with a 2.5pt brand-red bar on
the left edge.

## Rules that are not cosmetic

**Assets are inlined, never linked.** The logo travels as a base64 data URI.
These documents get printed from temporary directories, attached to gists and
mailed around, and a relative asset path survives none of that.

**PDF success is verified by inspecting the file.** Chromium exits 0 in several
situations where it prints nothing. `whisker.branding.pdf` checks that the output
exists and is non-empty. An earlier version trusted the exit code and reported
PDFs that were not there.

**The base theme keeps tables whole; long tables must opt out.** `alliance.css`
sets `page-break-inside: avoid` on tables, which is right for the small tables in
a report and wrong for a 250-row comparison. A long table has to set
`page-break-inside: auto` on itself and `avoid` on its rows, and should set
`thead { display: table-header-group }` so column headers repeat per page.

## If the reference changes

Re-derive, do not eyeball. Run:

```bash
python packages/whisker/benchmark/tools/extract_pdf_design.py <new.pdf> --out <dir>
python packages/whisker/benchmark/tools/extract_logo.py <new.pdf> --out-dir <dir>
```

The first reports fonts, text colours, vector fills and font sizes by character
volume. The second lifts the logo out by brand fill colour, since the reference
draws it as vector paths rather than embedding a raster. Update `alliance.css`
from those numbers, replace `cppalliance-logo.png`, replace
`LAYOUT-REFERENCE.pdf`, and re-run `packages/whisker/tests/test_branding.py`.
