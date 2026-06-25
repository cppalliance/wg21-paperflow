# 0002 - Typed Window union for per-source collection ranges

**Status:** accepted

## Context

[1-collection.md](../foundation/1-collection.md) models a source as a `sources` row with a
`config_json` and a cursor-based incremental sync ("what's new since I last looked?"). It
does not, on its own, say how much *history* a fresh source should pull. In practice the
boost-data collectors suffered a "must-seed / slow first run" problem: a new source either
starts empty and back-fills forever, or needs a manual seed. The foundation also spans
heterogeneous sources whose progress axis differs - a timestamp for an API, a **byte
offset** for the cumulative reflector mbox (1-collection.md's reflector note), and "current
only" for a feed.

## Decision

Add a typed `Window` union parallel to the typed `Cursor` union, stored per source as
`window_json`:

- `TemporalWindow(since, until)`, `ByteRangeWindow(max_bytes_per_sweep)`, `CurrentOnlyWindow()`.
- `ThrottleCeilings` for universal per-sweep caps and `BackfillState` for backward fill.
- Per-kind safe defaults so a fresh source is bounded by default and extended deliberately.

**Authority rule:** `cursor` is the single forward resume position; `window.range` is
operator intent (a first-sweep floor / `until` ceiling); `BackfillState` drives backward
extension so the forward cursor never rewinds. There is no dual temporal authority.

## Consequences

- Cures the slow-first-run problem; ranges are extendable later with safe defaults.
- One more per-source field; modeled as config-like, a faithful extension of `config_json`.
- The `byte-range` axis keeps the reflector's byte-offset sync first-class rather than
  forcing it into a temporal frame.
