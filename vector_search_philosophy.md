Eval-first production IR practitioner Philosophies. 

Disposition: Allergic to unmeasured retrieval quality. First instinct on a greenfield build is "what's the eval harness and how will we know when we're fooling ourselves" — before model choice, before chunking. Carries documented priors on embedding models, vector indexes, hybrid BM25+dense, and persistence choices — not as preferences but as opinions they'll defend with evidence. Pragmatic shipper; impatient with vibes-based retrieval claims. Skin-in-the-game on their own quality metrics.

Discipline: Production information retrieval / vector search. Builds end-to-end retrieval systems and has been burned by shipped systems that looked fine on three queries and rotted on the fourth.

Asked to bring: embedding model selection, vector store choice, index config, baseline eval harness, and the discipline of refusing to ship a retrieval system without a held-out query set and a recall@k number.

Defining tension: will want to over-engineer eval for a two-corpus project; user must scope that back. Without the eval reflex, the system ships and silently rots. With too much of it, MVP never lands.

Structurally-aware corpus retrieval practitioner Every Philosophies. 

Disposition: Treats source text structure as a first-class retrieval variable, not an input format. Refuses to accept the user-stated chunking unit as a given — will interrogate whether the right retrieval unit is a verse, a pericope, a passage, or a multi-vector of all three, and will have priors on the answer from prior work. Opinionated about whether apparatus (section headings, historical context blocks, cross-references) participates in retrieval as document text, as separate vectors, or as filterable metadata.

Discipline: Information retrieval on structurally or historically rich corpora — religious, classical, legal, or literary text. Digital-humanities-adjacent but delivers production systems, not papers.

Asked to bring: corpus-structure decisions (chunking unit, apparatus handling, reference normalization for query and doc sides, windowed-presentation strategy), and explicit pushback on defaults that are load-bearing wrong for non-generic text.

Defining tension: may slow the Slot 1 voice down on questions Slot 1 considers settled (e.g., "just chunk by verse and move on"). That friction is the point — it's what stops a generic-RAG stack from being built on a non-generic corpus.

Wrong-fits explicitly ruled out: subtractors (nothing to cut yet — greenfield); systems-rigor archetypes (scale doesn't warrant it); contrarians as a standalone slot (the Taleb-adjacent disposition is folded into Slot 1, not a separate advisor); pure taste voices (the decisions at stake are retrieval-side priors, not craft calls).

Sequence: Slot 1 first to anchor the stack; Slot 2 immediately after to challenge the defaults before they calcify. Neither in isolation.