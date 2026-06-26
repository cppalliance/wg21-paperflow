# Source matrix

The collection layer is source-agnostic: a source type is an adapter module + a
`SourceKind` value + a registry config schema. Concrete adapters land in later milestones;
this matrix records the planned shape so the contract (candidate type, change strategy,
cursor, window) is stable.

| SourceKind   | candidate  | change strategy   | cursor          | default window         | visibility |
|--------------|------------|-------------------|-----------------|------------------------|------------|
| `web`        | Discovered | conditional-GET   | OpaqueToken     | CurrentOnly            | public     |
| `rss`        | Discovered | conditional-GET   | OpaqueToken     | CurrentOnly            | public     |
| `mbox`       | Fetched    | mbox byte-offset  | ByteOffset      | ByteRange (10MB/sweep) | public     |
| `reflector`  | Fetched    | mbox byte-offset  | ByteOffset      | ByteRange (10MB/sweep) | private    |
| `slack`      | Fetched    | api-native        | Timestamp       | Temporal (since=today) | restricted |
| `github`     | Fetched    | api-native        | Composite       | Temporal (since=-90d)  | public     |
| `discourse`  | Fetched    | api-native        | Timestamp       | Temporal (since=-90d)  | public     |
| `discord`    | Fetched    | api-native        | MonotonicId     | Temporal (since=today) | private    |
| `reddit`     | Fetched    | api-native        | Timestamp       | Temporal (since=-90d)  | public     |
| `sitemap`    | Discovered | conditional-GET   | OpaqueToken     | CurrentOnly            | public     |
| `mcp`        | Fetched    | api-native        | OpaqueToken     | CurrentOnly            | restricted |

`mcp` visibility is derived per source from its registry config rather than being fixed by
the kind: a public server (e.g. `user-github`) maps to `public`, a private server (e.g.
`user-pinecone-search-private`) maps to `private`. `restricted` is the conservative default
recorded here for when a server's config does not declare one.

## Non-adapter roles

`role=group` rows are **not** adapters and have no `SourceKind`. They carry a `GroupKind`
(`github_org`, `reflector_host`, `discord_guild`) and are expanded into child
`role=source` rows by a discovery step (selection via include/exclude in the group's
`config_json`). New children land as `candidate`/`pending` for curation; vanished children
are demoted.
