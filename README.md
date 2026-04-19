# scripvec

Vector search over LDS scripture.

## Current scope

Simple, straightforward vector search across:

- The Book of Mormon
- The Doctrine and Covenants

No frills — query in, semantically similar verses out.

## Roadmap

Ordered roughly by distance from the current scope:

1. **Simple Q&A** — natural-language questions answered from retrieved verses, powered by multi-vector retrieval.
2. **1800s Webster's Dictionary expansion** — since the scripture language is not modern, run a Webster's 1828-era lookup against both the user's query and every verse in both corpora. Feed those definitions into the multi-vector index so archaic meanings transfer across the search.
3. **Scholarly commentary as multi-vector sources** — attach research and commentary to the verses they discuss, index them as additional vectors for those verses, and surface them alongside results.
4. **The Bible** — extend the corpus.

The far-future vision is a search where every returned verse carries along the scholarly conversation about it, with period-correct semantics baked into the retrieval itself.
