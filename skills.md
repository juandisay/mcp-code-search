# Code-Memory MCP — Skills & Module Catalog

> A comprehensive reference of all capabilities, modules, and optimization techniques in this MCP server.

---

## Module Map

| Module                 | Role                                                         | Key Classes/Functions                   |
| ---------------------- | ------------------------------------------------------------ | --------------------------------------- |
| `main.py`              | Entry point — runs as MCP server (`--mcp`), FastAPI, or CLI  | `mcp`, `app`, MCP tools, REST endpoints |
| `config.py`            | Environment-based configuration via `pydantic-settings`      | `Settings`, `config`                    |
| `core/indexer.py`      | File traversal, SQLite state management, ChromaDB upsert     | `CodeIndexer`                           |
| `core/ast_chunker.py`  | Tree-sitter based AST-aware code chunking                    | `ASTChunker`, `EXTENSION_TO_TS_LANG`    |
| `core/watcher.py`      | Real-time filesystem observer via `watchdog`                 | `ProjectWatcher`                        |
| `core/searcher.py`     | Semantic search with **Cross-Encoder Reranking**             | `CodeSearcher`                          |
| `core/mahaguru_client.py`| AI Cascading client for task refinement                    | `mahaguru_client`, `request_mahaguru_refinement`|
| `core/token_manager.py`| Token usage tracking and usage reporting                     | `token_manager`                         |
| `core/rule_manager.py` | Agent rules initialization and stack detection              | `rule_manager`                          |

---

## MCP Tools

### `semantic_code_search`
Search code using natural language queries with two-stage ranking.

| Parameter            | Type             | Required | Default | Description                                                |
| -------------------- | ---------------- | -------- | ------- | ---------------------------------------------------------- |
| `query`              | `string`         | ✅       | —       | Natural language description                               |
| `n_results`          | `integer`        | —        | `3`     | Max results after reranking                                |
| `project_name`       | `string`         | —        | `null`  | Filter by project name                                     |
| `max_distance`       | `float`          | —        | `null`  | Initial retrieval threshold (lower = stricter)             |
| `language`           | `list[string]`   | —        | `null`  | Filter by file extension(s) (e.g. `[".py", ".ts"]`)       |
| `re_rank`            | `boolean`        | —        | `True`  | Use Cross-Encoder to refine search results                 |

### `request_mahaguru_refinement`
Escalate complex tasks to a high-level planner model (Mahaguru).

| Parameter          | Type           | Required | Description                                     |
| ------------------ | -------------- | -------- | ----------------------------------------------- |
| `refinement_brief` | `string`       | ✅       | Problem summary and roadblocks                  |
| `relevant_files`   | `list[string]` | —        | Specific files to include in context            |

**Mechanism:** Automatically injects RAG context and file content (up to 30k tokens) into the request.

### `index_folder`
Index a local project folder with AST-aware splitting.

| Parameter     | Type     | Required | Description                 |
| ------------- | -------- | -------- | --------------------------- |
| `folder_path` | `string` | ✅       | Absolute path to the folder |

---

## FastAPI Endpoints

| Endpoint           | Method   | Description                                           |
| ------------------ | -------- | ----------------------------------------------------- |
| `/index`           | `POST`   | Trigger background indexing for a folder              |
| `/stats`           | `GET`    | Returns collection stats and indexed projects         |
| `/sync-rules`      | `POST`   | Initialize/Update `.agents` rules for a project       |
| `/health`          | `GET`    | Liveliness check                                      |

---

## Architecture Pipeline

```
Local Files → AST Chunking → Embedding (MiniLM) → ChromaDB → Reranking (Cross-Encoder) → Result
```

1. **State Check** — Uses SQLite to skip unchanged files (idempotent indexing).
2. **AST-Aware Chunking** — Splits by function/class boundaries instead of character counts.
3. **Producer-Consumer** — Parallel indexing with a dedicated writer thread.
4. **Two-Stage Search** — Fast vector retrieval followed by precise neural reranking.
5. **AI Cascading** — "Worker" models can call "Mahaguru" for architectural guidance.

---

## Configuration

| Variable                  | Default   | Description                                          |
| ------------------------- | --------- | ---------------------------------------------------- |
| `CHROMA_DATA_PATH`        | `data`    | ChromaDB storage directory                           |
| `MAHAGURU_API_KEY`        | _(empty)_ | API key for cascading to high-level models           |
| `USE_RERANKER`            | `True`    | Enable/Disable the Cross-Encoder stage               |
| `CROSS_ENCODER_MODEL`     | `...`     | `cross-encoder/ms-marco-MiniLM-L-6-v2`               |

---

## Optimization Tips

- **Real-Time Watcher** — Changes are patched incrementally; no need to re-index the whole folder.
- **Selective Reranking** — Disable `re_rank` for very large k-queries to save latency.
- **Sandbox Security** — `ALLOWED_CONTEXT_ROOTS` limits files accessible to the Mahaguru tool.
- **Token Tracking** — Every search/refinement reports token usage for cost monitoring.
