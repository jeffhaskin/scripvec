# ADR-009: Non-verse canonical text is sentence-packed under a per-chunk token cap, with a no-split floor

## Status

ACCEPTED

## Created

2026-04-20

## Modified

2026-04-20

## Supersession

*Supersedes:* none
*Superseded by:* none

## Date

2026-04-20

## Deciders

Jeff Haskin — engineer, sole decision authority at time of record.

## Context and Decision Drivers

`cr-001_vector_search_mvp.md` item 2 locks the verse as the atomic retrieval and display unit: verses are not chunked, never split, never windowed. That decision covers the body text of the Book of Mormon and the Doctrine and Covenants but leaves a gap. The bcbooks corpus (chosen in CR-001 item 1) also ships several pieces of non-verse canonical text — the BoM title page, the Testimony of the Three Witnesses, the Testimony of the Eight Witnesses, the pre-1921 BoM book-level headings, the 15 in-text 1830 chapter headings (Mosiah 9 & 23; Alma 5, 7, 9, 17, 21, 36, 38, 39, 45; Helaman 7 & 13; 3 Nephi 11; Mormon), and the per-section `signature` field on the D&C. None of these have a verse number. None of them fit the verse contract.

CR-001 item 3 records the engineer-approved policy that those non-verse items are chunked into the maximum number of consecutive sentences that fit under a per-chunk token cap, and indexed on equal footing with verses (same dense `vec0` table, same BM25 corpus). This ADR codifies that policy as a binding architectural decision and adds the structural refinement the engineer added at decision time: a no-split floor below which non-verse items are emitted as a single chunk regardless of the per-chunk cap, so an item only marginally above the cap does not produce a pathological tail chunk of a handful of tokens.

**Scope note — what this ADR does and does not lock.** This ADR locks *policies* and *structural decisions* about non-verse-text chunking: that the unit of chunking is *consecutive sentences* (not arbitrary token windows), that packing is *maximal* (greedy fit), that a no-split floor exists, that the floor must exceed the per-chunk cap, that the resulting chunks are indexed alongside verses, and that the token counter used for chunking must agree with the ADR-005 embed client's counter. It does **not** stipulate the numeric value of the per-chunk token cap, the no-split floor, or any other tunable knob. Per `docs/policies/domain_policies/adrs/pl-001_adrs_lock_policies_not_values.md`, those values live in the project-root configuration file. ADRs stipulating values that ought to be configurable settings are a category error and are rejected at authoring time.

**Decision drivers:**

- **The verse contract does not extend to non-verse canonical text.** Verses are short, uniformly-shaped, and addressable by `(book, chapter, verse)`. The title page, witness testimonies, pre-1921 book headings, in-text 1830 chapter headings, and D&C signatures are none of those things. A different rule has to govern them, and uniformity matters more than per-item specialization for an MVP-scale corpus.
- **Sentence-bounded chunking preserves semantic units.** Splitting on raw token windows or character counts can sever clauses mid-sentence, which degrades both embedding quality and the human-readability of any displayed chunk. Greedy sentence packing under a token cap is the established pattern for retrieval-corpus chunking in the LangChain / LlamaIndex / Haystack ecosystem and matches how the bge / Qwen-family embedders were trained against natural-language passages.
- **A no-split floor avoids pathological tail chunks.** Without a floor, an item of cap+1 tokens splits into one cap-sized chunk plus one single-token chunk; the tail chunk is useless for retrieval and pollutes the index. The floor's invariant — *floor > cap* — guarantees that any item which does get split has each chunk meaningfully populated.
- **The token counter must match the embed-side counter.** A chunk that fits the chunker's local counter but exceeds the embed client's 8K cap (ADR-005) would raise at index time. A chunk that fits the embed counter but the local counter would have split into two would silently violate the cap policy. One counter, shared across the boundary, is the only consistent rule.
- **Index uniformity is a feature.** Verses and non-verse chunks live in the same dense vector table and the same BM25 corpus, so the existing query path (CR-001 dense top-k, BM25 top-k, RRF fusion) requires no second code path to incorporate apparatus. The retriever returns whatever scores best, regardless of unit kind, and the result type carries the metadata that distinguishes them downstream.

## Decision

Non-verse canonical text in the indexed corpus is chunked, persisted, and retrieved according to the following binding policies. Each is binding on `corpus_ingest`, on the retrieval index schema, and on every change to either thereafter.

### 1. Chunking unit — consecutive sentences

- The chunker emits chunks composed of **one or more consecutive sentences** from the source item, in document order.
- A chunk never splits a sentence mid-sentence. The smallest indivisible unit the chunker can produce is one whole sentence.
- The sentence-splitter implementation is a value-level / library-level choice and is not fixed by this ADR. It lives in `corpus_ingest`. Changing the splitter is a code-review concern, not an ADR amendment.
- Pure character-window or pure token-window chunkers (which may split mid-sentence) are rejected by this policy.

### 2. Packing rule — greedy maximal fit under the per-chunk token cap

- Sentences are packed greedily into the current chunk in document order. A new sentence is added if and only if the chunk's resulting token count remains at or below the per-chunk token cap. When the next sentence would exceed the cap, the current chunk is closed and a new chunk begins with that sentence.
- The per-chunk token cap is **configurable** in the project-root config file. **This ADR does not stipulate its value.** Hard-coding the cap in module code is a code-review-grade rejection.
- A single sentence that on its own exceeds the per-chunk cap is a corpus-quality bug, not a runtime case to silently coerce. The chunker raises (ADR-001 fail-loud); the source content is fixed or the cap is raised.

### 3. No-split floor — items below the floor are emitted whole

- Any non-verse item whose total token count is **at or below the no-split floor** is emitted as exactly one chunk regardless of the per-chunk cap.
- Items strictly above the no-split floor are subject to the greedy sentence-packing rule (item 2), which may produce one chunk or many depending on the item's length and sentence boundaries.
- The no-split floor is **configurable** in the project-root config file. **This ADR does not stipulate its value.** Hard-coding the floor is a code-review-grade rejection.
- **Invariant — `floor > cap`.** The no-split floor must strictly exceed the per-chunk token cap. Otherwise the policy is ill-defined: an item below the floor would be emitted whole at a length the cap forbids, contradicting the cap. The chunker validates this invariant at config load and raises if violated (ADR-001).
- Rationale: this guarantees that any item which does get split has every chunk meaningfully populated — the smallest possible split-tail chunk under a `floor > cap` regime is bounded below by `(floor - cap)`, plus or minus sentence-boundary alignment, never an arbitrarily small tail.

### 4. Token counter — shared with the embed client

- The token counter the chunker uses to evaluate the per-chunk cap and the no-split floor is the **same counter** the ADR-005 embed client uses to enforce its 8K-token input cap.
- A divergent counter is a code-review-grade rejection. One counter, one source of truth, one boundary check.
- The counter is supplied by the embed client module and consumed by the chunker via the embed module's public surface, not duplicated.

### 5. Index uniformity — chunks live alongside verses

- Every chunk produced by this policy is stored as a record in the same dense `vec0` table and the same BM25 corpus that hold verse records.
- A chunk's record carries the same shape as a verse record on the dimensions retrieval cares about (`record_id`, embedding, BM25-tokenized text, surface text), and additional metadata (kind, source-item identifier, position within source) sufficient to identify it as a non-verse chunk and resolve it back to its source item.
- The retrieval query path (dense top-k, BM25 top-k, RRF fusion) makes no distinction between verse records and non-verse-chunk records. The unit kind is metadata on the result, not a control-flow split in the retriever.
- The `record_id` namespace is shared but distinguishable: verse records use the existing `verse_id` derivation; non-verse chunks use a derivation that is similarly stable, deterministic, and human-readable, but unmistakably not a verse id. The exact id scheme is an implementation choice in `corpus_ingest`, not fixed by this ADR.

### 6. Scope — non-verse canonical text only

- This policy governs the *canonical non-verse text* the corpus source provides: BoM title page, Testimony of the Three Witnesses, Testimony of the Eight Witnesses, pre-1921 BoM book-level headings, the 15 in-text 1830 chapter headings, and the D&C `signature` field. Any future canonical non-verse content the source begins to ship (e.g., if bcbooks adds back excluded apparatus) is automatically in scope.
- Verses themselves are out of scope — they are governed by CR-001 item 2 and remain atomic.
- Non-canonical apparatus (modern italicized chapter summaries, footnotes, cross-references, study aids) is out of scope of both CR-001 and this ADR. Any future inclusion of such content is a separate decision and a separate CR / ADR.
- Scholarly commentary attached as multi-vector sources (per `docs/specs/vision_tree/000_overall_vision.md`) is out of scope. That layer will get its own chunking decision when it is built.

## Consequences

**Positive:**

- One uniform rule covers every piece of non-verse canonical text, present and future. Adding a new canonical apparatus element does not require a new chunking decision.
- Sentence-bounded chunking preserves semantic units, which is what the embedder expects and what a human reader expects when a chunk is surfaced as a result.
- The no-split floor with `floor > cap` guarantees no pathological tail chunks. The smallest split-tail chunk is bounded below by `floor - cap` (modulo sentence-boundary alignment), not by zero.
- Per-chunk cap and no-split floor live in exactly one place (the project-root config file). Re-tuning either is a one-line config edit, never an ADR amendment, never a code search.
- Index uniformity means the existing dense + BM25 + RRF query path requires no second code path to handle apparatus. The retriever sees records; metadata on the result tells the caller what kind of record it is.
- The shared token counter eliminates a class of bugs at the chunker / embed-client boundary — chunks that pass the chunker's check but fail the embed client's check, or vice versa.

**Negative:**

- A poorly-tuned cap or floor produces a poorly-shaped index. The configurability is a feature, but it is also a knob someone has to choose well. This ADR provides no guidance on what value to choose; the project-root config file owns that decision and any subsequent tuning.
- A chunk-level result returned to the user looks different from a verse-level result. Display logic downstream must distinguish the two; consumers of the CLI's JSON output must read the kind metadata on each result. This is the cost of index uniformity.
- The chunker has to load and apply a sentence-splitter library (e.g., NLTK punkt, spaCy, regex-based). That is a new dependency surface. Whatever library is chosen, its determinism and offline-availability are required (the build pipeline does not call out for a model download at index time).
- A single-sentence item that exceeds the cap raises rather than being silently truncated. That is correct per ADR-001 but means the engineer (or a future contributor) must occasionally fix corpus content rather than relying on the chunker to coerce it.
- Mixing chunk records with verse records in the same RRF fusion can introduce ranking comparisons across heterogeneous units. The expectation is that the embedder + BM25 score on text content alone, indifferent to unit kind, but the failure mode is worth flagging: a query that semantically matches both a verse and the title page may produce ordering surprises in the top-k. Eval (CR-001 / former-CR-002 harness) is the gate; the failures file surfaces such cases.

## Validation

- The chunker module in `corpus_ingest` reads both the per-chunk token cap and the no-split floor from the project-root config file. Hard-coded numeric values are rejected at code review.
- At config load, the chunker asserts `floor > cap` and raises if the invariant is violated (ADR-001).
- A unit test asserts that an item of token count `≤ floor` produces exactly one chunk regardless of the cap.
- A unit test asserts that an item of token count `> floor` is split into chunks each of token count `≤ cap`, and that no chunk is empty.
- A unit test asserts that no chunk splits a sentence — every chunk is a contiguous sequence of whole sentences from the source.
- A unit test asserts that the chunker's token counter and the embed client's token counter agree on a battery of fixed inputs (including non-ASCII, punctuation-heavy, and contraction-heavy strings).
- A unit test asserts that a single-sentence input exceeding the per-chunk cap raises with a message naming both the sentence's token count and the cap (ADR-001 — fail loud, no silent truncation).
- The chunking parameters (cap, floor) are part of the index identity: they are included in the CR-001-defined `config.json` BLAKE2b hash so that drift between config and index state is refused loudly per ADR-001 and CR-001's endpoint-drift / corpus-drift guards.

## Links

- `docs/specs/adrs/001_accepted_no_silent_failures.md` — the chunker inherits the fail-loud posture: oversize sentences, invariant violations, and counter mismatches all raise rather than coerce.
- `docs/specs/adrs/005_accepted_embedding_model_and_endpoint.md` — the embed client and its 8K-token cap. The chunker's per-chunk cap is independent of this 8K cap (the chunker's cap is much smaller), but the *counter* used to evaluate both must be the same one.
- `docs/specs/adrs/006_accepted_serialize_embedding_calls.md` — chunk records, like verse records, are embedded serially through the single sanctioned embed client. Chunking does not introduce a parallel embed path.
- `docs/policies/domain_policies/adrs/pl-001_adrs_lock_policies_not_values.md` — the policy under which this ADR's per-chunk cap and no-split floor are kept out of the ADR text and pushed to the project-root config file.
- `cr-001_vector_search_mvp.md` — item 2 (verses are atomic) and item 3 (non-verse text is sentence-packed under a token cap) are the CR decisions this ADR codifies and refines.
- `docs/principles/001_vector_retrieval.md` — the eval-first disposition. Chunking parameters are gated by the eval harness like any other tunable.

## Conflicts surfaced

- **CR-001 item 3 currently embeds the literal `512 tokens per chunk` value in its decision text.** Per `pl-001_adrs_lock_policies_not_values.md` (which applies to CRs as well as ADRs), that stipulation must be removed and replaced with a reference to the project-root config file. The drive-by edit is performed at the same time this ADR is committed; CR-001 item 3 is updated to point at this ADR and at the config file rather than naming the cap value inline. The same applies to the no-split floor introduced in the engineer's 2026-04-20 refinement: the ADR text frames it as configurable, and the value is held in config, not in CR-001.
- **No project-root config file exists yet.** This ADR introduces a second subsystem (after the reranker, ADR-008) whose tunable values are defined to live in the project-root config file. The file format and exact filename are still pending the CR that introduces and owns the file. Until that CR lands, the chunker must read the cap and the floor from a code-local fallback that is explicitly marked as a transitional placeholder; the placeholder is removed when the project-root config file ships. This deferment is auditable: it is recorded here, and it is revisited each time a third subsystem requires a config-resident value.
- **None vs ADRs 001–008.** No conflicts.

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| 2026-04-20 | created | initial authoring — codified greedy sentence packing under a configurable per-chunk token cap, added the configurable no-split floor with the `floor > cap` invariant, fixed the shared-token-counter rule with the embed client, and locked index uniformity (chunks alongside verses) for non-verse canonical text. No values stipulated; cap and floor live in the project-root config file. | Jeff Haskin |
