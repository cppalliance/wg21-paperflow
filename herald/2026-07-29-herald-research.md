# Building a Continuous AI Journalism Pipeline

A fully autonomous AI newsroom - one that crawls the web, detects novelty, clusters stories, writes articles, and publishes continuously - is buildable today with commodity components. The pipeline, not the LLM, is the defensible product. Total cost at moderate scale (200 articles/day) runs $2,000-5,000/month. EU AI Act Article 50 takes effect August 2, 2026, requiring AI disclosure unless substantive human editorial review is documented.

## Key Findings

The system decomposes into five stages. Each stage has a mature tool ecosystem and proven architectural patterns. Production systems (Independent Wire, Pub.cat Cybertron, PressNow) demonstrate the full loop running 24/7. The critical insight repeated across every successful deployment: multi-agent adversarial review with deterministic quality gates separates working systems from embarrassing ones (CNET's 53% error rate without them vs. 97.4% pipeline completion with the Four-Layer Model).

---

## The Five-Stage Pipeline

```
CRAWL  ->  DETECT  ->  CLUSTER  ->  WRITE  ->  PUBLISH
  |          |            |           |           |
Scrapy    SimHash      BERTopic    Agentic     Strapi v5
Crawlee  MinHash+LSH    spaCy    multi-agent   Ghost
Firecrawl  Fisher       Neo4j    RAG+verify    Dagster
  |       geometric       |           |           |
Kafka      Flink        Kafka      Quality     CMS API
                              gates
```

---

## Stage 1: Web Crawling

### Architecture

The Mercator two-tier frontier (priority queues + per-host politeness queues) partitioned by hostname hash remains the universal design for distributed crawling. Kafka coordinates URL distribution. Bloom filters handle URL dedup. WARC-on-S3 stores raw content.

### Tool Selection

| Scenario | Tool | Why |
|----------|------|-----|
| Python team, static HTML at scale | Scrapy | 59K stars, largest plugin ecosystem, 2,800 pages/min |
| Modern SPAs, JS-heavy sites | Crawlee | Unified API, browser fingerprint randomization, proxy rotation |
| LLM/RAG pipeline, managed | Firecrawl | Zero-infrastructure, returns LLM-ready markdown, 96% coverage |
| LLM/RAG pipeline, self-hosted | Crawl4AI | Full control, no per-request costs, Apache 2.0 |
| Real-time streaming at enterprise scale | StormCrawler | 60% more efficient than Nutch, continuous processing |

### Performance Reality

Plain HTTP crawling is 40x faster than headless browser crawling per page (1,100+ pages/min vs 320). The winning pattern is hybrid: attempt HTTP first, fall back to Playwright only when JS rendering is actually needed. A 4GB VPS handles hundreds of static pages/sec; the same VPS handles 4-6 Playwright tabs.

### Data Sources for News

| Source | Volume | Cost |
|--------|--------|------|
| GDELT 2.0 | 400K articles/day, 15-min updates | Free (URLs only) |
| Common Crawl News | 600K articles/day, full HTML | Free (self-hosted processing) |
| RSS/Atom feeds | Varies per site | Free |
| Trawl unified API | YouTube, Reddit, SEC, news, podcasts | Paid |
| Exorde | 3M+ posts/hour, 200+ platforms, 176 languages | Paid |

### Politeness

RFC 9309 standardized robots.txt but intentionally excluded Crawl-delay. Build adaptive rate limiting from 429/503 response signals. Default 1-2 seconds between requests to the same host. The EU AI Act now gives robots.txt and ai.txt compliance legal weight for AI training data collection.

---

## Stage 2: Novelty Detection

### Three-Tier Deduplication

Process in order - each tier catches what the previous one misses:

1. **Exact (SHA-256)**: Catches 60-70% of duplicates at near-zero cost. Hash normalized content after stripping boilerplate.
2. **Near-duplicate (SimHash 64-bit)**: Hamming distance <= 3 bits = near-duplicate. Google's crawler has used this since 2007.
3. **Set similarity (MinHash + LSH)**: 5-word shingles, 128 permutations, Jaccard >= 0.85 threshold. Catches paraphrased content SimHash misses.

### News-Specific Dedup

NDD-MAC (NAACL 2025) handles the paywall challenge - when you only have headlines and snippets. Combines Sentence-BERT embeddings + metadata augmentation + Louvain community detection to correctly group articles that share entities, timeframes, and sources but differ in phrasing.

Working thresholds for news:
- Jaccard >= 0.85: duplicate
- Jaccard 0.70-0.85: escalate to semantic check
- Cosine >= 0.92: semantically duplicate
- Below both: distinct story

### Breaking News Detection

**Volume-based (simple):** Track entity mention rate. Fire when count > mean + 3*stddev within window. GDELT uses 15-minute heartbeats.

**Fisher-geometric (advanced):** Monitors information geometry of emerging clusters. Detects narrative convergence from as few as 6-8 articles before volume spikes by measuring covariance collapse below the Cramer-Rao noise floor. Designed for: pandemic outbreaks, coordinated government actions, disinformation campaigns, market-moving disclosures.

### Incremental Crawling

Conditional GET with ETag/If-Modified-Since saves 80-95% of bandwidth. Layer validators: ETag (high reliability) -> content hash (authoritative) -> sitemap lastmod (low reliability, priority hint only). Typical change rate: 5-10% of corpus per cycle.

### Stream Processing Stack

Kafka 4.x (KRaft mode, no ZooKeeper, tiered storage) + Flink 2.x (unified batch/streaming, native vector search and ML inference in SQL). Exactly-once semantics via Flink checkpointing + Kafka transactional sink. This is the de facto standard for real-time event processing at scale.

---

## Stage 3: News Feed Creation

### Clustering with BERTopic

BERTopic + HDBSCAN is the 2026 consensus for news clustering - outperforms LDA, NMF, and Top2Vec on coherence and scalability.

```python
from bertopic import BERTopic
from umap import UMAP
from hdbscan import HDBSCAN

umap_model = UMAP(n_neighbors=15, n_components=5, random_state=42)
hdbscan_model = HDBSCAN(min_cluster_size=150, prediction_data=True)

topic_model = BERTopic(umap_model=umap_model, hdbscan_model=hdbscan_model)
topics, probs = topic_model.fit_transform(docs)
```

For streaming: compute embedding for new article, compare against existing cluster centroids (cosine > 0.7-0.8 merges, below creates new cluster), periodically re-cluster to correct drift.

### Entity Extraction and Knowledge Graph

Production pipeline: spaCy `en_core_web_trf` for NER -> entity linking against Wikidata/DBpedia -> LLM-based relation extraction via `spacy-llm` -> Neo4j knowledge graph storage.

Node types: Person, Organization, Location, Event. Edge types: works_at, located_in, participated_in, involves. Properties: confidence scores, source articles, timestamps.

### Event Threading

Goes beyond flat topic clustering - models the internal structure of a news story as a directed graph of events with temporal and causal dependencies.

ACDT algorithm: `distance(a,b) = alpha * cos_sim(a,b) + beta * time_decay(a,b) + gamma * entity_overlap(a,b)`

5W1H approach: extract Who, What, When, Where, Why, How from each article as vectorized pseudo-passages. Apply hierarchical agglomerative clustering with complete linkage using both timestamp and pseudo-passage similarity.

### Ranking Formula

```
score(article) = w1 * freshness(exponential_decay, half_life_hours)
               + w2 * authority(source)
               + w3 * relevance(article, user_profile)
               + w4 * popularity(article)
               + w5 * diversity_bonus(article, feed)
```

Freshness half-lives: breaking news 2 hours, analysis 24 hours, evergreen 168 hours.

### Taxonomy

IPTC Media Topics (1,200+ hierarchical terms, 17 top-level categories) is the industry standard. Pre-trained classifier on HuggingFace: `classla/multilingual-IPTC-news-topic-classifier` (xlm-roberta-large, 100+ languages). Use confidence threshold >= 0.90 for high-precision classification.

### Feed Architecture

Kappa architecture (stream-only) with Kafka + Flink for real-time processing. Nightly Spark batch for model retraining, full re-clustering (drift correction), knowledge graph rebuilding, and source credibility updates. Fan-out on write for active users, fan-out on read for long-tail.

### Credibility

Multi-Agent Fact-Checking (MAFC) framework: multiple specialized agents verify claims against different information sources independently. Critical design principle: separate factual veracity from source credibility (a tabloid can publish careful investigative work; a prestigious broadsheet can frame facts misleadingly).

---

## Stage 4: AI Article Writing

### Architecture: Orchestrator-Led Agentic Workflows

Single-prompt generation is obsolete. The 2026 standard decomposes the editorial cycle into specialized agents with quality gates between each stage:

| Agent | Responsibility |
|-------|---------------|
| Research Agent | Source aggregation, data extraction, real-time fact-checking |
| Drafting Agent | Narrative composition, tone alignment, inverted pyramid structure |
| Fact-Check Agent | Claim verification, citation generation, confidence scoring |
| SEO Agent | Keyword density, heading hierarchy, schema markup |
| Publishing Agent | Multi-channel scheduling, social metadata |
| Orchestrator | Pipeline management, quality gates, human escalation |

### Fact Verification

RAG with strict citation contracts cuts unsupported claims by 60-80%. Multi-agent adversarial verification using different model families prevents correlated hallucination. Top models now hallucinate at 1-2% rates (down from 38% in 2021).

Key guardrails:
- Every factual claim must cite a specific source from provided context
- If context does not support a claim, model must say "information not available"
- Never fabricate quotes, statistics, dates, or names
- Use a different model family for verification than for generation
- Claims with confidence > 85% auto-proceed; < 85% goes to editorial review

### Quality Scoring (100-Point Framework)

| Dimension | Weight | Threshold |
|-----------|--------|-----------|
| Factual Accuracy | 25 pts | Claims verified against sources |
| Source Attribution | 15 pts | Every claim attributed |
| Structural Integrity | 15 pts | Inverted pyramid, heading hierarchy |
| Readability | 10 pts | Flesch-Kincaid, sentence length |
| SEO/GEO Optimization | 10 pts | Keywords, schema, meta |
| Originality | 10 pts | No > 25 consecutive words from source |
| Style Alignment | 10 pts | AP style compliance, tone match |
| Freshness | 5 pts | Current information, recent sources |

Action thresholds: >= 80 auto-publish, 60-79 human review, < 60 reject and rewrite.

### Style Control

Define voice as a behavioral system: sentence structure rules, vocabulary constraints (banned words, attribution verbs), tone anchors, and proof requirements. Style transfer by example (paste 80-150 words of target voice) carries more signal than adjective lists.

### Multi-Source Synthesis

MASS-RAG framework (ACL 2026): Evidence Summarization Agent condenses sources, Evidence Extraction Agent pulls key facts, Reasoning Agent analyzes relationships, Synthesis Agent reconciles into coherent narrative. Separate what's consensus from what's conflicting. For conflicts: present both positions with attribution.

---

## Stage 5: Continuous Operations

### Orchestration

**Dagster** (recommended): Asset-centric model maps to articles, source databases, topic clusters. Native freshness policies trigger re-processing when sources update. Built-in lineage tracks provenance.

**Temporal**: Right choice for long-lived workflows that must survive crashes (waiting for human review, multi-step verification chains).

**Airflow 3.x**: Viable if already invested. New `@task.agent` decorator for multi-step LLM agents, `durable=True` for cached execution, `AIBudget` for cost caps.

### Architecture Pattern: Hybrid (Recommended)

```
[Cron Layer]
  Schedule -> Crawl -> Cluster -> Batch Generate -> Quality Gate -> Publish Queue

[Event Layer]
  Signal Stream -> Priority Filter -> Urgent Pipeline -> Quality Gate -> Immediate Publish

[Shared]
  Source Database, Agent Pool, Quality Gate Logic, CMS Integration
```

Cron provides baseline coverage and cost efficiency. Event layer handles breaking stories with higher priority and cost tolerance.

### CMS Integration

**Strapi v5** (recommended): Native MCP server (GA in v5.49), AI agents do CRUD directly, open-source, self-hosted.

**Ghost**: If you want built-in newsletters, membership, and SEO without rebuilding.

Markdown is the canonical intermediate format. Generate in markdown, store in markdown, convert at the CMS layer. Integration pattern: AI Pipeline -> Markdown -> CMS API (create as draft) -> Quality gate -> Publish -> Webhook -> Frontend rebuild.

### Cost at Scale

| Scale | Articles/day | Monthly Cost |
|-------|-------------|--------------|
| Solo publisher | 10-20 | $100-300 |
| Small newsroom | 50-100 | $500-1,500 |
| Medium operation | 200-500 | $2,000-5,000 |
| Large scale | 1,000+ | $10,000-30,000 |

Per-article cost with model routing: $0.15-0.40 (vs $2-5 using frontier models for everything).

Top optimization levers: model routing (40-60% savings), batch API for non-real-time (50% discount on batched share), prompt caching (30-70% on cached portion).

### Monitoring

- Pipeline completion rate (target: > 95%)
- Average story processing time (Four-Layer Model achieves 135 seconds)
- Fact-check score distribution
- Rejection rate (too high = wasted compute, too low = quality concern)
- Token usage and cost per article
- Source diversity index

Alert on: pipeline stall, rejection rate spike > 50%, cost anomaly > 2x average, quality score degradation.

### Self-Correcting Pattern

GraphNews implements bounded revision loops: Writer -> Critic (score < 8/10 loops back to Writer, max 3 attempts, then finalize anyway). The "Hallucination Brake" - a max revision counter - prevents infinite loops and runaway API costs. Essential for any autonomous system.

---

## Legal Compliance

### EU AI Act Article 50 (Effective August 2, 2026)

- AI-generated text on matters of public interest must be disclosed
- Exception: substantive human review + named person holds editorial responsibility
- "Substantive" means more than cursory approval - rubber-stamping does not qualify
- Machine-readable markings required (C2PA or similar)
- Fines: up to EUR 15 million or 3% of worldwide annual turnover
- No grandfather clause for existing systems

### US Legal Landscape

- Public data scraping is legal post-hiQ v. LinkedIn (9th Cir.)
- FTC Section 5 prohibits deceptive practices - AI content presented as human-written could violate
- No comprehensive federal AI disclosure law yet; state-level laws emerging

### Compliance Strategy

1. Always label AI-generated content visibly
2. Implement machine-readable provenance metadata
3. Publish AI methodology transparency page
4. Store full generation chain (sources, prompts, model versions, intermediate outputs)
5. If claiming editorial exemption: document substantive review process with named responsible person

---

## Open-Source Reference Implementations

| Project | Architecture | Status |
|---------|-------------|--------|
| Independent Wire | 12 agents, 5 models, 80 sources, 18 language streams | Live at independent-wire.org (AGPL-3.0) |
| Skeptik | Multi-agent (Agno), deterministic gates, zero-editorial | Functional demo |
| AI Journalist | Hexagonal architecture, domain-agnostic, pluggable ports | v0.8.2 (MIT) |
| Agentic Newsroom | Four-agent Claude Code pipeline, PR-based review | Functional (MIT) |
| GraphNews | LangGraph cyclic graph, self-correcting critic loop | Demo |
| Pub.cat Cybertron | 13 modules, one-operator multi-brand | SaaS beta |

Common technical choices across projects: LangGraph for orchestration, OpenRouter for LLM routing, Tavily for search/extraction, Postgres + pgvector for storage, Next.js for frontend.

---

## Recommended Technology Stack

| Layer | Primary | Alternative |
|-------|---------|-------------|
| Crawling | Scrapy + Firecrawl | Crawlee, Crawl4AI |
| Message queue | Kafka 4.x (KRaft) | NATS JetStream, Redis Streams |
| Stream processing | Flink 2.x | Kafka Streams (simple topologies) |
| Dedup | SimHash + MinHash + LSH | Milvus 2.6 native MINHASH_LSH |
| Embedding | all-mpnet-base-v2 | all-MiniLM-L6-v2 (faster) |
| Clustering | BERTopic + HDBSCAN | Incremental cosine similarity |
| NER | spaCy en_core_web_trf | GLiNER (zero-shot) |
| Knowledge graph | Neo4j | NetworkX (prototype) |
| LLM routing | LiteLLM / OpenRouter | Direct provider APIs |
| Agent framework | LangGraph | Agno, custom Python |
| Orchestration | Dagster | Temporal, Prefect |
| Storage | Postgres + pgvector | SQLite (prototype) |
| CMS | Strapi v5 (MCP-native) | Ghost |
| Frontend | Astro or Next.js | Hugo |
| Monitoring | LangFuse + Prometheus | LangSmith |
| Feed output | RSS 2.0 + JSON Feed 1.1 | Atom, WebSub push |

---

## Lessons from Production

1. **The pipeline is the product.** Models are commodity. Orchestration, source tiering, quality gates, and editorial calibration are the defensible value.
2. **Multi-agent adversarial review is non-negotiable.** Every system without it (CNET) failed publicly.
3. **Transparency wins.** Every successful implementation (AP, Independent Wire, Pub.cat) prominently discloses AI involvement.
4. **Start with structured, high-volume content.** AP started with earnings reports. Scale to complex journalism only after proving the system on simpler tasks.
5. **Deterministic gates over LLM judgment for publish decisions.** Algorithmic reject criteria (specific thresholds, max revision counts, hallucination brakes) prevent both quality failures and cost explosions.
6. **Fisher-geometric detection beats volume-based.** Can detect breaking stories from 6-8 articles before volume spikes.
7. **Hybrid cron + event architecture is the production consensus.** Neither pure real-time nor pure batch serves news well alone.
8. **EU AI Act compliance from day one.** Retroactive compliance is expensive; designing for transparency upfront is cheap.

---

## Sources

### Web Crawling
- RFC 9309 (Robots Exclusion Protocol, IETF 2022)
- EDPB Opinion 28/2024 on AI models
- Scrapy, Crawlee, StormCrawler, Firecrawl, Crawl4AI documentation
- Common Crawl architecture references
- GDELT Project, Trawl, XPOZ, Exorde documentation
- hiQ Labs v. LinkedIn (9th Cir. 2022)

### Novelty Detection
- NDD-MAC (NAACL 2025)
- RagSEDE (WWW 2026) - RAG + structural entropy
- Fisher-Geometric Framework (Zenodo 2026)
- Conformal Event Prediction (ACL 2026)
- Temporal-Guided News Stream Clustering (EMNLP 2023)
- text-dedup, Milvus 2.6, LSHBloom documentation

### News Feed
- BERTopic documentation and benchmarks
- IPTC Media Topics taxonomy
- Chronicle, Miniflux, FreshRSS architecture
- Multi-Layer AI Framework for Information Landscape Analysis (2026)
- MAFC (Multi-Agent Fact-Checking) framework

### AI Writing
- Agentic Newsroom (github.com/mindaugasnakrosis/agentic-newsroom)
- AI-Press (ACL 2025), MAS-TLS / Agent Newsroom (ACL 2026)
- MASS-RAG (ACL 2026), TRUST Agents (arXiv 2026)
- Data Journalist Agent (SAO Workshop 2026)
- Reuters Institute: How will AI reshape the news in 2026?
- AP Stylebook 58th Edition (2026)
- CrawlQ BRAND Score Methodology (2026)

### Continuous Operations
- Four-Layer Model (Sharma et al., March 2026) - 97.4% completion, 135s/story
- EU AI Act Article 50 Guidelines (European Commission, July 2026)
- EU Code of Practice on Transparency of AI-Generated Content (June 2026)
- Independent Wire, Skeptik, Pub.cat Cybertron, PressNow documentation
- CNET AI content incident (2022-2023), Sports Illustrated (2023)
- Dagster, Temporal, Airflow 3.x documentation
- Strapi v5 MCP server documentation

*2026-07-29 16:39 - claude-opus-4-6-thinking-high*
