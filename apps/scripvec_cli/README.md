# scripvec_cli

The single MVP deployable — a Typer-backed command-line interface that accepts a query string and returns top-k verses from the Book of Mormon and Doctrine and Covenants.

Allowed in-repo imports: `packages/retrieval` only (per the dependency graph in `docs/specs/adrs/003_accepted_mvp_folder_structure.md`).

---

## `vex` CLI — Command Reference

**Entry point:** `vex` (registered as `scripvec_cli`)

---

### Root

```
vex [--version | -V]
```

Global flag: `--version / -V` — outputs JSON `{cli_version, embedding_model, latest_index_hash}` and exits.

---

### `vex query <TEXT>`

Search scripture verses.

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--k` | `-k` | int | `10` | Number of results |
| `--mode` | `-m` | enum | `hybrid` | `bm25` \| `dense` \| `hybrid` |
| `--format` | `-f` | enum | `json` | `json` \| `text` |
| `--index` | `-i` | str | `"latest"` | Index hash or `"latest"` |
| `--show-scores` | — | bool | `false` | Include scores in output |

**JSON output shape:**
```json
{
  "query": "...",
  "mode": "hybrid",
  "k": 10,
  "index": "<hash>",
  "latency_ms": {...},
  "results": [
    {"rank": 1, "verse_id": "...", "ref": "...", "text": "...", "forced": false}
  ]
}
```

**Exit codes:** `0` success · `1` user error · `2` index not found · `3` upstream/embedding error

---

### `vex version`

Outputs same JSON as `--version` flag: `{cli_version, embedding_model, latest_index_hash}`

---

### `vex index build`

Build search index from corpus.

| Flag | Default | Description |
|------|---------|-------------|
| `--from-scratch` / `--incremental` | `--from-scratch` | Full rebuild (incremental not yet supported) |
| `--rebuild-corpus` | `false` | Allow corpus drift and rebuild |

**JSON output:** `{"index_hash": "<hex>", "latest": true}`

---

### `vex index list`

List all built indexes.

**JSON output:** array of `{hash, created_at, model, dim, is_latest}`, sorted by hash ascending.

---

### `vex eval run`

Run evaluation suite against an index.

| Flag | Default | Description |
|------|---------|-------------|
| `--queries` | `data/eval/queries.jsonl` | Path to queries JSONL |
| `--judgments` | `data/eval/judgments.jsonl` | Path to judgments JSONL |
| `--index` | `"latest"` | Index hash or `"latest"` |
| `--format` | `"json"` | `json` \| `text` |

**JSON output shape:** `{index_hash, metrics[], recall10_by_bucket, ship{hybrid_beats_bm25_recall10, dense_beats_bm25_recall10, index_size_under_400mb, all_passed}, failures_path}`

---

### `vex feedback feedback`

Record relevance feedback for a query result.

| Flag | Required | Description |
|------|----------|-------------|
| `--query-id` | yes | Query ID |
| `--verse-id` | yes | Verse ID to rate |
| `--grade` | yes | `0`, `1`, or `2` |
| `--note` | no | Optional note string |

**JSON output:** `{"status": "recorded", "query_id": "...", "verse_id": "...", "grade": N}`
