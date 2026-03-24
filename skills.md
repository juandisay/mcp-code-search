# Code-Memory MCP — Skills & Module Catalog

> A comprehensive reference of all capabilities, modules, and optimization techniques in this MCP server.

---

## Module Map

| Module                 | Role                                                         | Key Classes/Functions                   |
| ---------------------- | ------------------------------------------------------------ | --------------------------------------- |
| `main.py`              | Entry point — runs as MCP server (`--mcp`) or FastAPI server | `mcp`, `app`, MCP tools, REST endpoints |
| `config.py`            | Environment-based configuration via `pydantic-settings`      | `Settings`, `config`                    |
| `core/indexer.py`      | File traversal, AST-aware chunking, ChromaDB upsert          | `CodeIndexer`                           |
| `core/ast_chunker.py`  | Tree-sitter based AST-aware code chunking                    | `ASTChunker`, `EXTENSION_TO_TS_LANG`    |
| `core/watcher.py`      | Real-time filesystem observer via `watchdog` for incremental indexing | `ProjectWatcher`, `IndexerEventHandler` |
| `core/searcher.py`     | Semantic vector search with advanced metadata filtering      | `CodeSearcher`                          |
| `core/token_manager.py`| Token usage tracking and reporting                           | `TokenManager`, `token_manager`         |
| `core/rule_manager.py` | Agent rules initialization and sync                          | `rule_manager`                          |

---

## MCP Tools

### `semantic_code_search`

Search code using natural language queries.

| Parameter            | Type             | Required | Default | Description                                                |
| -------------------- | ---------------- | -------- | ------- | ---------------------------------------------------------- |
| `query`              | `string`         | ✅       | —       | Natural language description (e.g. _"S3 upload function"_) |
| `n_results`          | `integer`        | —        | `3`     | Max results to return                                      |
| `project_name`       | `string`         | —        | `null`  | Filter by project name                                     |
| `max_distance`       | `float`          | —        | `null`  | Override relevance threshold (lower = stricter)            |
| `language`           | `list[string]`   | —        | `null`  | Filter by file extension(s) (e.g. `[".py", ".ts"]`)       |
| `file_path_includes` | `string`         | —        | `null`  | Only match files whose path contains this substring        |
| `excluded_dirs`      | `list[string]`   | —        | `null`  | Exclude results from these directories                     |

### `index_folder`

Index a local project folder into ChromaDB.

| Parameter     | Type     | Required | Description                 |
| ------------- | -------- | -------- | --------------------------- |
| `folder_path` | `string` | ✅       | Absolute path to the folder |

**Returns:** files processed, files skipped (unchanged), chunks upserted.

### `list_indexed_projects`

List all project names currently stored in the database. No parameters.

### `get_index_stats`

Show database statistics: total chunks, collection name, storage path, and project list. No parameters.

---

## FastAPI Endpoints

| Endpoint | Method | Description                                                      |
| -------- | ------ | ---------------------------------------------------------------- |
| `/index` | `POST` | `{"folder_path": "/path"}` → triggers background indexing        |
| `/stats` | `GET`  | Returns chunk count, collection name, storage path, project list |
| `/docs`  | `GET`  | Interactive Swagger UI                                           |

---

## Architecture Pipeline

```
Local Files → Smart Chunking → Embedding (all-MiniLM-L6-v2) → ChromaDB → Semantic Search
```

1. **File Traversal** — Walk directory tree, skip excluded dirs, filter by supported extensions
2. **Hash Check** — SHA-256 content hash to skip unchanged files on re-index
3. **Smart Chunking** — Language-aware splitting via `langchain-text-splitters` (13 languages)
4. **Batch Upsert** — Configurable batch size to reduce ChromaDB write overhead
5. **Vector Search** — Cosine similarity query with optional distance threshold and project filtering

---

## Supported Languages

| Extension | Language   | Extension | Language |
| --------- | ---------- | --------- | -------- |
| `.py`     | Python     | `.rb`     | Ruby     |
| `.js`     | JavaScript | `.rs`     | Rust     |
| `.ts`     | TypeScript | `.php`    | PHP      |
| `.jsx`    | JavaScript | `.c`      | C        |
| `.tsx`    | TypeScript | `.cpp`    | C++      |
| `.go`     | Go         | `.cs`     | C#       |
| `.java`   | Java       | `.html`   | HTML     |
| `.md`     | Markdown   | `.css`    | Generic  |

Also supports `.json`, `.yaml`, `.yml`, `.toml`, `.cfg`, `.ini` with generic splitting.

---

## Configuration

All settings via environment variables or `.env`:

| Variable                  | Default   | Description                                          |
| ------------------------- | --------- | ---------------------------------------------------- |
| `CHROMA_DATA_PATH`        | `data`    | ChromaDB storage directory                           |
| `PROJECT_FOLDER_TO_INDEX` | _(empty)_ | Auto-index this folder on startup                    |
| `CHUNK_SIZE`              | `1000`    | Characters per chunk                                 |
| `CHUNK_OVERLAP`           | `200`     | Overlap between adjacent chunks                      |
| `BATCH_SIZE`              | `100`     | Chunks per ChromaDB upsert batch                     |
| `MAX_DISTANCE`            | `2.0`     | Default cosine distance threshold (lower = stricter) |

---

## Optimization Tips

### Indexing Performance

- **Real-Time Watcher** — The MCP server runs a background watcher. Once indexed, saving or deleting a file automatically patches ChromaDB precisely without full folder scans.
- **Skip unchanged files** — Enabled automatically via hash caching; re-indexing a folder only processes modified files
- **Batch size** — Increase `BATCH_SIZE` for large projects (500–1000) to reduce I/O overhead
- **Chunk tuning** — Increase `CHUNK_SIZE` (e.g. 1500) for dense code; decrease for small utility functions

### Search Quality

- **Lower `MAX_DISTANCE`** to `1.0`–`1.2` for stricter relevance (fewer but better results)
- **Use `project_name` filter** to scope results to a specific codebase
- **Use `language` filter** (e.g. `[".py"]`) to restrict results to specific file types in polyglot repos
- **Use `file_path_includes`** (e.g. `"/core"`) to search only within a specific directory subtree
- **Use `excluded_dirs`** (e.g. `["tests", "vendor"]`) to omit noisy directories from results
- **Increase `n_results`** to `10` when exploring unfamiliar codebases

### Resource Management

- ChromaDB stores data on disk; the `data/` folder grows with indexed repos
- Embedding runs on CPU via sentence-transformers; first load may take a few seconds
- RAM usage stays under 1GB for up to ~50,000 chunks (PRD §7)

---

## Excluded Directories

Files inside these directories are automatically skipped during indexing:

`node_modules`, `.git`, `venv`, `.venv`, `__pycache__`, `.tox`, `.mypy_cache`, `.pytest_cache`, `dist`, `build`, `.eggs`, `.idea`, `.vscode`

---

## Troubleshooting

| Issue                                | Solution                                                                                          |
| ------------------------------------ | ------------------------------------------------------------------------------------------------- |
| "No relevant code snippets found"    | Index the folder first with `index_folder`, or lower `max_distance` threshold                     |
| Slow first search                    | Embedding model loads on first use — subsequent queries are fast                                  |
| Files not being indexed              | Check file extension is supported (see table above)                                               |
| Re-index doesn't update              | File content hash hasn't changed — edit the file or clear the hash cache by restarting the server |
| ChromaDB errors on small collections | Handled automatically — `n_results` is clamped to collection size                                 |
