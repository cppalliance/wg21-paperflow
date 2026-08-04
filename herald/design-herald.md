# Herald: A Continuous C++ Ecosystem Journalism System

Building Herald produces a continuously-running publication. It crawls a human-curated set of C++ ecosystem domains, notices what changed, groups the changes into stories, writes several AI drafts of each story in distinct journalist voices, and publishes the one a human editor picks - all through the wg21.org website, on owned hardware, with no cloud model in the loop.

## Executive summary

Herald is one of paperflow's continuous outputs, a peer to Agora and the per-person Dossiers. It turns the open flow of C++ ecosystem activity - papers, mailings, conference talks, library releases, vendor moves, community threads - into published journalism without a human writing any prose. A human does one thing: choose, from a slate of machine-written drafts, which one runs.

The design rests on a small number of decisions that shape everything else. Herald and wg21.org share one Postgres database, so Herald needs no read/write API and no auth of its own; the editor works in wg21.org's existing Django interface. Collection is deterministic Python with no model calls, and it hands work downstream through an ordered, replayable event log. Language models enter only at the writer and at source curation, and they run on owned hardware through the shared `pipeline` package, never against a cloud API. The writer does not try to produce one perfect article; it over-generates diverse drafts and lets the editor curate, because regenerating an LLM draft is cheap and perfecting one is not. Diversity comes from routing each draft to a different member of a fine-tuned specialist fleet, not from temperature jitter. The prose register is locked to clinical parliamentary analysis; where Herald is funny, the subject matter is funny, never the writing.

Most of Herald's collection design already tracks 2026 industry practice closely - conditional GET, RFC 9309 robots handling, front-door-first fetching, graceful degradation against an AI-hostile edge, and a deliberate, evidence-backed choice of MinHashLSH over SimHash for news near-duplicates. The research this document was reconciled against confirms those choices rather than overturning them. Three places downstream, where the earlier design was thinner, adopt existing practice outright: the intelligence layer clusters stories by embedding similarity with first-story detection rather than by an unresolved hand-tuned heuristic; the writer verifies drafts with a cite-or-omit contract and an adversarial cross-specialist check, and scores them so the editor's slate arrives ranked; and publication carries an explicit AI-authorship disclosure that doubles as the record of the human editorial review the EU AI Act requires.

A reader deciding whether to build this should know the central bet: throughput over per-article polish, bought with cheap regeneration and a fast human selection step, defended against error by a fail-closed sufficiency gate, provenance that runs from raw bytes to published citation, and a hard rule that private-source material informs but never appears in published text.

## Key design choices

1. **wg21.org integration is a shared database, not an API.** Herald's tables live in the same Postgres that the wg21.org Django application uses; Django views read and mutate them directly. The editor is whoever `request.user` is on a permission-gated Django page, so Herald authenticates nobody and exposes no read or write API. This removes an entire service tier and auth system. Reversing it is expensive once both codebases write the shared schema and data has landed: a later split means inventing a service boundary, a wire format, and an auth handshake that do not exist today.

2. **No language model runs in collection.** Fetching, extraction, deduplication, change detection, and person observation are classical Python; models appear only at the writer and the source-curation Feed Proposer. The high-volume path that must be correct stays deterministic and cheap to replay, matching the existing paperflow discipline of mechanical parts mechanical, analytical parts analytical, with an explicit seam between them. The tension is that identity resolution and clustering feel like they want a model, which is why they live in a distinct intelligence layer rather than leaking into collection.

3. **Collection hands off through a transactional outbox log.** Every fetch writes its blob first, content-addressed by sha256, then commits a single Postgres transaction that writes both the metadata rows and the `collection_events` rows, then issues a NOTIFY. Consumers each track a cursor into that ordered log. The result is atomic at the consumer boundary - no consumer ever sees an event whose blob is missing, or metadata without a matching event - and adding a consumer or replaying all of history is trivial. Reversing it is costly: the event kinds and their ordering are a persisted contract that intelligence, the candidate harvester, the research-desk embedder, and the fine-tuning export are all written against.

4. **Content identity is keyed on text, and near-duplicates collapse with MinHashLSH.** Forty outlets reprinting one wire story become forty `urls` rows pointing at one `contents` row, because identity is the sha256 of extracted text, not the URL. Near-duplicates with minor edits collapse through datasketch MinHashLSH at 128 permutations, 5-token shingles, and a 0.9 threshold. SimHash was considered and rejected on evidence: on news-domain near-duplicate detection MinHash scored F1 0.95 against SimHash's 0.79 and ran nine times faster. This is the on-disk primary-key structure of the corpus, so it is expensive to change after data lands; the accepted cost is that MinHash indexes use more memory than a 64-bit fingerprint would.

5. **Change is judged on canonicalized plaintext, in four outcomes.** The fetcher classifies every check as unchanged, cosmetic, real, or failure by comparing the hash of extracted text, never raw HTML, so ad rotation and session tokens never manufacture a story while a corrected article does. Filtering boilerplate before diffing is what keeps the signal clean. This contract is the foundation the entire event system depends on, so its four categories are load-bearing.

6. **Fetching looks for the front door first, inside a 2026 bot-etiquette envelope.** Herald prefers a feed, sitemap, API, or bulk dump and scrapes HTML only when nothing structured exists, escalating through four tiers of bot-defense only as far as a source forces. It sends RFC 9309-correct robots handling, explicit conditional GET, `Retry-After` honoring, two distinct user-agent identities for training versus live-retrieval, and request signing ready for Web Bot Auth. The 2026 edge drops unsigned AI crawlers regardless of what robots.txt permits, so this is table stakes rather than courtesy; a blocked source is recorded and demoted rather than fought, because Herald does not want an arms race with Cloudflare.

7. **Draft diversity comes from routing across a self-hosted specialist fleet.** All model calls go through the `pipeline` package to self-hosted vLLM/SGLang endpoints - a frontier general model plus five or six fine-tuned specialists of roughly 7 to 32 billion parameters. A six-draft slate pulls one draft each from the frontier model and several specialists via a data-driven routing table, so variety is a property of which model wrote each draft, not of temperature noise. Owned hardware running around the clock makes cost-per-token a non-input and makes routing-for-diversity free. Any design that assumes a cloud API call is broken by construction against this operating model.

8. **The writer over-generates; a human curates; unpicked drafts age out.** The writer produces several drafts per story tuned for diversity of angle, the editor sees them side by side and picks one in about a minute, and the losers age out per a freshness window while remaining as training signal. This exploits the asymmetry that models are cheap to regenerate and hard to perfect, while humans are slow to produce and fast to select. The editor's tool is therefore a selection interface, not an editing one, and nitpicking a single draft is explicitly out of scope. The trade is per-article polish for throughput, which only pays off if the slate carries real angle diversity.

9. **The writer runs seven steps and fails closed.** Catalog, shape triage, evidence retrieval, brief, journalist selection, draft, handoff. The brief builder either assembles enough material for a publishable story or returns "insufficient" and discards the hypothesis; there are no partial briefs. The brief itself is the shared factual backbone - who, what, when, where, quotes with attribution, research-desk background with provenance, visibility-tagged sources - and it is journalist-agnostic, because angle, tone, and voice belong to the persona, not the facts. Conservatism drops borderline stories, which is acceptable because the catalog re-surfaces them the next day if they still matter.

10. **The research desk is pgvector inside the shared Postgres.** During briefing and drafting, a single query returns background chunks that each carry source URL, publish date, and visibility for citation, combining semantic similarity with relational filters and keyword search in one statement. Putting the vector index in the shared database makes relational joins free, carries provenance with no duplication, and adds no new service or backup surface. The embedding dimension is baked into the chunk table, which is the one costly-to-reverse element, mitigated by the table being a rebuildable materialized view over the corpus.

11. **The register is locked, so comedy stays involuntary.** No specialist prompt contains "humor," "sardonic," or "wit"; the register is serious political-journalism analysis that never acknowledges absurdity. Instructing a model to be funny produces performed comedy, whereas a clinical register colliding with absurd committee behavior produces the real thing. The cost is giving up the obvious lever - telling the model to be witty - in favor of the operator choosing subject matter where the collision fires.

12. **Visibility gates republication, not ingestion, and the corpus is dual-use.** A visibility value of public, private, or restricted rides every content row from the moment it enters, and the writer enforces that private-source material - reflector posts, Slack messages - can inform a brief but is never quoted in a published article. The same corpus is simultaneously the specialist fleet's fine-tuning training set, filtered by the same column. Herald ingests everything because the principal operates it, but publication and public-corpus training must respect source confidentiality. Visibility is a data-lifecycle property, expensive to retrofit, so it is present from ingestion.

13. **[Adoption] Intelligence clusters by embedding, with first-story detection.** The earlier design left topic clustering as an unresolved "M sources within K hours" heuristic and disagreed with itself over whether intelligence was pure Python or model-driven. Herald adopts incremental centroid clustering over the same `minilm` embeddings the research desk already produces, with first-story and novelty detection to flag genuinely new stories. Because embedding arithmetic is not a generative model call, this resolves the contradiction cleanly: intelligence stays free of generative LLMs while still clustering semantically.

14. **[Adoption] The writer verifies and scores before the editor sees anything.** The earlier design leaned on the sufficiency gate, research-desk grounding, and the human pick, with no explicit fact-check. Herald adopts a cite-or-omit contract in which every factual claim traces to a research-desk chunk or an evidence item or is cut, an adversarial check run by a different specialist family than the one that wrote the draft, and a quality rubric that ranks the slate. The rubric ranks; it never auto-publishes. The human pick stays the decision, so this strengthens the over-generate-and-curate philosophy rather than replacing it.

15. **[Adoption] Publication discloses AI authorship, and the disclosure is the compliance record.** The earlier design carried provenance but nothing reader-facing. Herald adopts EU AI Act Article 50 disclosure on every published article. Herald's human-editor-picks workflow is precisely the substantive human editorial review the Article 50 exemption describes, so the disclosure paired with an editorial-responsibility record is what keeps Herald on the right side of the rule while still labeling honestly.

## Integration is a shared database, not a service boundary

wg21.org is a Django and Postgres application, and Herald shares its Postgres database. That single decision collapses most of what a publishing system would otherwise need. Herald's tables - `sources`, `urls`, `contents`, the person tables, `briefs`, `drafts`, `published_articles`, `editorial_actions` - live in the same database wg21.org queries, so the website's Django views read published articles and render editor pages by talking to those tables directly. There is no read API for articles, no editor API, and no user-facing HTML served by Herald.

What Herald does expose is deliberately tiny: an Atom feed rendered as a Django view over Herald's rows, a small internal trigger API for operations such as "re-generate this slate now" or "mark this source unhealthy," and a Prometheus `/metrics` endpoint. Editor authentication is Django's own - an editor page is a view gated by a permission check on `request.user`, and Herald authenticates no one. Cloudflare R2 is shared the same way, one bucket namespaced by prefix, with Django using `django-storages` and Herald using `fsspec`.

The reason is economy of moving parts, and the reason it is stated as a key choice is that it is costly to unwind. Once both codebases write the shared schema and the corpus has accumulated, separating Herald into its own service means introducing a wire protocol, a synchronization story, and an authentication handshake that the shared-database design specifically avoids. The design accepts tight coupling to wg21.org in exchange for having no integration surface to build or secure.

The seam between mechanical and analytical work runs through the whole system and is worth stating on its own. Collection performs no model calls at all. Language models appear at exactly two places: the writer, and the Feed Proposer that curates new sources. This is why the pipeline can replay its entire history cheaply, why the fetch path is deterministic, and why the parts that must be correct are not at the mercy of a model's output.

## Collection is deterministic and event-sourced

Collection is the foundation every downstream layer consumes. It ingests continuously from every source class relevant to the C++ ecosystem - general web, RSS and Atom, sitemaps, public mailing lists, private WG21 reflectors, and MCP servers - and presents each source uniformly as a stream of `(canonical_url_or_uri, bytes_or_text, content_type, metadata)` behind a common adapter interface. Adding another reflector or another index touches nothing but a source registration.

### An ordered event log is the contract between stages

The layer's outputs feed several independent consumers: intelligence, the source-curation candidate harvester, the research-desk embedder, and the fine-tuning export. Rather than have each poll for changes, collection emits an explicit event log using the transactional outbox pattern. The ordering within a single fetch is the load-bearing part. The blob is written first, content-addressed and idempotent. Then one Postgres transaction writes the metadata rows and the event rows together and commits. Then NOTIFY wakes any listener. A consumer therefore never observes an event whose blob has not landed, and the only possible leak - a blob with no metadata, from a transaction that failed after the blob write - is harmless and swept by a periodic garbage collector.

The event kinds are a public contract, because consumers are written against them:

| Kind | Emitted when |
|---|---|
| `content_first_seen` | A content hash never seen before is stored |
| `content_changed` | An existing URL now yields different canonicalized text |
| `url_disappeared` | A URL that returned content now 404s or 410s |
| `url_resurrected` | A previously-disappeared URL returns content again |
| `candidate_observed` | An outbound link or feed reference appears in extracted content |
| `content_re_extracted` | A batch reprocess upgraded the extractor over existing bytes |
| `person_candidate_observed` | A name or handle matched, or partially matched, a known person |

Each consumer keeps a named cursor into the log and processes forward from it. Two properties follow and both are design goals rather than incidental: a new consumer is added by inserting a cursor row and writing a handler, changing collection not at all; and a replay is a cursor reset to zero, which is how "we changed the clustering heuristic, re-derive everything" or "the extractor improved, re-emit everything" are handled. Consumer lag is observable as the gap between the maximum event id and each cursor, exported as a gauge.

### Identity is text, not URL

Herald stores two `sha256` content identities on the `contents` row: a strict hash over NFC-normalized, whitespace-collapsed text, and a fuzzy hash over NFKC-casefolded, punctuation-stripped text. The strict hash catches identical content and the fuzzy hash catches content that differs only in formatting or Unicode normalization. The `urls` and `contents` split means syndication is free to represent: many URLs point at one content row, and each source relationship is retained as metadata because knowing that eight outlets carried the same story is itself signal.

The change-detection contract classifies each fetch into four outcomes, and the distinction between the middle two is the reason it operates on extracted text:

| Outcome | Condition | Effect |
|---|---|---|
| Unchanged | 304, or raw-byte hash matches | Update `last_checked_at` only |
| Cosmetic | Raw bytes differ, extracted text identical | Update timestamps, no new version row |
| Real | Extracted text differs | New `contents` row, new version row, blob stored |
| Failure | Non-2xx, timeout, or robots-disallowed | Record status, schedule backoff retry |

Diffing raw HTML would produce nothing but noise from ad rotation, view counters, and session tokens, so Herald filters first through the extractor and diffs the canonicalized text, using paragraph-hash diffing plus a correction-keyword regex to notice inserted "correction" and "editor's note" language.

### Fetching is polite by necessity, not just courtesy

Herald reaches for structured access before scraping: a feed, a sitemap, a REST or GraphQL API, or a bulk dump, and only failing all of those does it scrape HTML. When scraping is unavoidable it escalates through four tiers - a plain async client with a real user-agent, then a Chrome TLS-fingerprint client, then a headless browser, then a commercial proxy - and stops at the lowest tier that works, with most traffic living in tier one. The politeness stack is explicit: RFC 9309 robots parsing via protego, per-host rate limiting keyed on the registered domain, `Retry-After` honored ahead of exponential backoff with jitter, and conditional GET implemented directly rather than through a transparent cache, because the change-detection contract needs the clean "unchanged" signal that a cache would hide.

The 2026 landscape is why this is a key choice rather than a detail. Edge providers now drop unsigned AI crawlers before the origin sees the request, regardless of robots.txt, so Herald plans for Web Bot Auth request signing from the start, runs two declared identities for training-input collection versus live retrieval, and publishes its address ranges and a bot documentation page. When a source sits behind an AI-hostile edge, Herald records the block in the source's `access_state` and demotes the source rather than escalating, surfacing "this source is blocked" to the editor instead of fighting an arms race.

### Where existing practice and Herald agree, and where Herald wins

This is the part of the system most saturated with current practice, so the reconciliation is mostly confirmation. Conditional GET, robots correctness, front-door-first fetching, and graceful edge degradation are exactly what a 2026 crawler should do, and they are already the design. Two divergences from the generic newsroom stack are deliberate and evidence-backed rather than uninformed. The generic three-tier deduplication stack would add a SimHash near-duplicate tier; Herald omits it because MinHash outperforms SimHash on news-domain near-duplicates by a wide margin in both accuracy and speed. And the generic pipeline reaches for Scrapy; Herald hand-rolls on aiohttp and asyncio because Scrapy's Twisted reactor fights an asyncio stack and Herald's sources are polled rather than crawled, so the frontier machinery Scrapy exists to provide is machinery Herald does not need.

## People are dossiers, resolved in three phases

Herald maintains a per-person knowledge base on every individual relevant to the C++ ecosystem, and organizations as a lighter-weight lookup. The boundary is deliberate: committee roles, papers, talks, libraries, employment, public statements, and death are in scope, while marriage, family, religion, and hobbies are not. Death is explicitly in scope for two reasons - the writer must never speak of a dead person as living, and the accumulated event history is the feedstock for an obituary.

`person` is the entity directly; there is no polymorphic `entities` table, a deliberate rejection of the generic-entity pattern because people carry specific attributes - names, handles, affiliations, committee roles - that do not generalize and would otherwise be forced into JSON. The dossier is an append-only `person_event` log plus writer-generated `person_claim` assertions, with name variants, platform handles, email domains, affiliations, committee roles, and directional relationships as satellite tables. The event log back-fills an `article_id` when a published piece cites an event, creating a two-way link between dossier and output.

Identity resolution is the hardest problem here and it runs in three phases across two layers. Collection does mechanical lookup in pure Python: a unique handle such as a GitHub username or ORCID, or an email domain paired with an exact family name, auto-links immediately, while a name-only match never does and instead produces a pending candidate. The intelligence layer then runs a fine-tuned sentence classifier that extracts only identity-defining sentences - "John Smith, concurrency expert at NVIDIA" rather than "John Smith walked to the podium" - and a verification step that pairs those sentences with the candidate profile and returns yes, no, or unsure, escalating only the unsure verdicts to the frontier model. Every confirmed new spelling is written back as a name variant, so the mechanical lookup catches it next time and the model is never asked twice, which makes the system cheaper as it runs. Merges and splits are audited in a resolution log.

## Intelligence clusters by embedding

This layer consumes the event log and decides what is worth writing about, distinct from editorial, which decides what is worth publishing. The earlier design left this layer underspecified - clustering was an open "M sources publish about the same thing within K hours" heuristic, and the layer was described in one place as pure Python and in another as model-driven. Herald resolves both by adopting embedding-based clustering, which is current practice for exactly this problem and which happens to dissolve the contradiction.

Stories form by incremental centroid clustering over the `minilm` embeddings the research-desk embedder already produces as content arrives. A new item is compared to existing cluster centroids by cosine similarity; a close match joins and updates the centroid, and a distant one seeds a new cluster. First-story and novelty detection flag when an item is genuinely new rather than another voice on an existing story, which is what turns a stream of content into a set of stories with a moment of origin. Because this is embedding arithmetic and nearest-centroid assignment rather than a generative model call, the layer keeps the "no generative LLM in intelligence" property the earlier design wanted while still clustering semantically. Explicit entity watches and manual editor seeding remain as additional ways a topic can form, and the layer assembles an evidence package - the content rows, their source attribution, and the relevant entities - for each story it emits.

A batch re-clustering pass can run periodically to correct the drift that any incremental clusterer accumulates, replaying from the event log the same way every other consumer does.

## The writer over-generates for a human to curate

The writer turns the intelligence layer's stories into publishable drafts, and its governing philosophy is the most consequential choice in the system. Herald does not try to write one good article. It writes several and lets a human pick, because an LLM is cheap to regenerate and expensive to perfect, while a human is slow to write and fast to choose. Showing an editor eight drafts and asking for a pick costs about ninety seconds; polishing one draft costs thirty minutes. Everything downstream bends to this: the writer optimizes for diversity of angle rather than for a single best output, the editor's tool is a selection interface rather than an editing one, and the losing drafts are retained as signal rather than discarded.

### Seven steps, failing closed

The pipeline runs daily in seven steps. It builds a lightweight catalog of what is new, each entry roughly 50 to 100 tokens of metadata so that a busy day's several hundred items fit whole in one context window with no retrieval needed. It triages that catalog against the shape registry, using deterministic hard triggers for shapes such as "a new mailing dropped" and model-assessed soft triggers for judgments such as "is this paper contentious." It retrieves the full text of the cited evidence for each surviving story. It builds a brief. It selects journalists by beat. It generates one draft per selected journalist. It hands the slate to the editor.

The sufficiency gate at the brief step is what keeps the editor's slate trustworthy. The brief builder either assembles enough for a publishable story or it returns "insufficient" and discards the hypothesis - no partial briefs, the same fail-closed discipline the rest of paperflow uses. A story that does not hold up once its full evidence is read is dropped and logged, so the triage model's false-positive rate stays observable and its prompts tunable, and the story returns tomorrow if it still matters.

### The brief carries facts; the persona carries voice

The brief is the shared factual backbone of a story and it is journalist-agnostic: who, what, when, and where; key quotes with source attribution; background from the research desk with full provenance; a source list tagged by visibility so the writer knows what may be quoted versus what merely informed the brief; and suggested angles the evidence supports. What the brief deliberately omits is angle, tone, and voice. Those live in the journalist persona, a stored configuration object loaded as a system prompt, carrying a beat that determines eligibility, a set of characteristic angles, and prose-style descriptors. The roster is small and curated, four to six journalists, each covering several shapes, so that two to four eligible journalists produce recognizably different takes on the same facts. Selection is a mechanical beat-tag intersection with a cap, no model involved.

Draft generation is where the specialist fleet does its work. Each selected journalist's draft is routed to a different member of the fleet through a data-driven routing table, so a slate's variety is a function of which model wrote each draft rather than of temperature noise - the architectural payoff of the over-generate strategy. During drafting the journalist has the research desk as a callable tool and can look up historical context mid-draft, receiving chunks with provenance it can cite. Every call goes through `pipeline.run_agent` with determinism invariants intact and prompt-injection defense on the untrusted web-sourced evidence via `pipeline.tools.wrap_source`. Each draft is stored as a typed object - headline, standalone lede, markdown body, attributed pull quotes, internal source references, and the generating model for later pick-rate analysis - and the set of drafts sharing a brief is the slate.

### The register is locked

No specialist carries humor, wit, or sardonic instruction in its prompt. The register is locked to the precision a parliamentary correspondent brings to a legislature, and it never acknowledges absurdity, because a model told to be funny performs comedy while a clinical register colliding with absurd subject matter produces comedy without intent. Different specialists still yield different textures - a terse-news voice and an editorial-commentary voice read differently - but none is trying to be funny. The operator conjures the effect by choosing subject matter, not by loosening the register.

### The research desk is the morgue file

The research desk is Herald's internal reference library, a semantic index over the entire accumulated corpus implemented as pgvector on the shared Postgres. The choice to co-locate it with the relational data is what makes it cheap: a single query filters by date, source, person, visibility, and content type and ranks by semantic similarity, all in one statement, with provenance returned in the same result set through foreign-key joins and no metadata duplication. Keyword search over `tsvector` rides alongside the vector search in the same query, catching exact paper numbers and library names that pure semantic ranking would miss.

The query contract that the writer depends on returns provenance with every chunk and respects visibility:

```sql
SELECT rc.chunk_text, c.title, c.source_url, c.publish_date, c.visibility
FROM research_chunks rc
JOIN contents c ON rc.content_hash = c.content_hash_text
WHERE rc.embedding <=> $query_embedding < $threshold
  AND c.publish_date > $since
  AND c.visibility = 'public'
ORDER BY rc.embedding <=> $query_embedding
LIMIT 20;
```

The embedder is a `collection_events` consumer that paragraph-chunks and embeds new content as it arrives, so the index is transactionally consistent with the corpus. Internet search is a restricted fallback, used only to check whether something has changed since collection last fetched it, or to fill a gap the editor explicitly flags. The journalist works from the curated archive the way a newspaper reporter works from the morgue file, with the open web as a last resort.

### The writer verifies before the editor sees the slate

The earlier design trusted the sufficiency gate, research-desk grounding, and the human pick to hold quality, with no explicit verification step. Herald adopts three practices that current automated-journalism systems treat as standard, positioned so they strengthen the curate philosophy rather than compete with it. Every factual claim in a draft must trace to a research-desk chunk or an evidence item under a cite-or-omit contract, and an unsupported claim is cut rather than published. An adversarial check runs each draft past a specialist from a different model family than the one that wrote it, so correlated hallucination does not survive review. And a quality rubric scores each draft on factual grounding, attribution, structure, and register fit.

The rubric ranks the slate; it does not gate publication. The editor still picks, and the score only orders the drafts the editor sees, because the human decision is the point of the whole design and an auto-publish path would contradict it. This is the difference between Herald and a fully autonomous pipeline: the verification makes the slate cleaner and better-ordered, and the human still chooses.

## Editorial selection and publication

The editor opens a story's slate in wg21.org and sees the brief, the evidence, the source list, and the drafts side by side, each with its journalist byline and now its quality rank. A form post picks one draft, which flips its state to approved and moves it to published; rejects the slate, which flips all drafts to rejected; or defers. Approved articles are rendered by wg21.org's reader pages querying `published_articles` directly - static rendering is not on the table. Unpicked drafts age out per the story's freshness window, swept by a periodic worker, and every editorial action is logged for pick-rate analysis by journalist, shape, and generating model, which is the feedback signal that eventually tunes the specialist fleet.

Source curation follows the same propose-and-curate pattern as article selection. A candidate harvester consumes the event log, scans new content for outbound links and citations, and populates a candidate pool. A Feed Proposer, the second of the two places a model runs, periodically ranks that pool by domain reputation, citation frequency from trusted sources, topical relevance, and feed availability, and writes ranked candidates with its reasoning to a pending list. The editor accepts, rejects with a cooldown that prevents the same dead blog being re-proposed weekly, or defers, and an accepted source begins being polled. Sources move through a `candidate` to `pending` to `active`, `rejected`, or `demoted` state machine.

Publication carries an explicit AI-authorship disclosure, the third adoption. Herald's articles are AI-written on matters of public interest, which under EU AI Act Article 50 must be disclosed unless the content has had substantive human editorial review and a person holds editorial responsibility. Herald's entire workflow is that review - a human editor reads a slate and chooses what runs - so the design pairs a visible disclosure with a stored editorial-responsibility record tying each published article to the editor who picked it. The disclosure is honest labeling and the record is the compliance evidence, and together they let Herald publish under the exemption rather than in spite of the rule.

## Cross-cutting constraints

Two properties run through every layer and are stated here rather than repeated in each.

Visibility gates republication, not ingestion. Herald ingests from private reflectors and Slack because the principal operates it, and every content row carries a public, private, or restricted visibility value from the moment it enters. That value governs what the writer may quote: private-source evidence can shape a dossier, influence importance, and inform a brief, but it cannot be directly quoted in a published article, and the writer must paraphrase or find a parallel public source. The same column governs the corpus's second use as fine-tuning data for the specialist fleet, where private content may train internal-use specialists but is filtered out of public-corpus training sets. Because visibility is a data-lifecycle property that is expensive to retrofit onto already-ingested content, it is present from the first write.

All model hosting is self-hosted through the `pipeline` package against owned hardware, and cloud APIs are out of scope by construction. The fleet is a frontier general model as a floor plus five or six fine-tuned specialists co-located on B300-class hardware, each optimized for one thing and deliberately weak at everything else. This is the constraint that makes routing-for-diversity affordable and the constraint that invalidates any design step assuming a metered API call.

## Roads not taken

Several components from the generic 2026 newsroom stack were considered and set aside, each for a reason grounded either in a hard constraint or in evidence.

Cloud model APIs lose to the operating model. Owned hardware runs continuously with data sovereignty and throughput as the optimization targets, so a metered external API is both unnecessary and contrary to the confidentiality the private sources require.

Scrapy loses to the shape of the workload. Its Twisted reactor fights an asyncio stack, and its reason for existing - frontier management for broad crawls - is machinery Herald does not need, because Herald polls a curated source list rather than crawling the open web.

SimHash loses to MinHash on evidence. For news-domain near-duplicate detection, the case Herald actually faces, MinHash scored markedly higher F1 and ran nine times faster, so the generic recommendation to layer a SimHash tier would cost accuracy and speed here.

Kafka, Dagster, Airflow, and Temporal lose to the workload shape and the integration choice. Those are tools for a directed-acyclic graph of batch jobs; Herald is a continuous polling and event-consuming system whose durable log is a Postgres table it already shares with wg21.org, so `procrastinate` covers periodic scheduling on that same Postgres without introducing a second stateful service.

BERTopic as a primary clusterer loses to the streaming requirement. Herald's stories form incrementally as content arrives, so incremental centroid clustering with first-story detection fits the stream, while a batch topic model is at most the periodic drift-correction pass rather than the primary path.

The consistent pattern is that Herald's infrastructure choices are bound by real constraints - self-hosted models, a shared database, a curated and polled source set - while its algorithmic choices defer to existing practice wherever practice has a solved answer, which is why the three adoptions concentrate in the layers the earlier design had left thin.

*2026-07-29 - Opus 4.8 (Cursor agent).*
