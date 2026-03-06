# Phase 3: APIs and MCP Integration

## Objective

Expose the core engine via a FastAPI app and the MCP protocol.

## Tasks

1. **FastAPI Server (`main.py`)**
   - Initialize FastAPI app.
   - Add REST endpoints:
     - `POST /index`: Accepts a JSON payload `{"folder_path": "..."}` to trigger indexing of a specific folder.
     - `GET /stats`: Returns ChromaDB stats (number of indexed chunks, collections, etc.).
2. **Auto-Indexing on Startup**
   - Use FastAPI lifecycle events (e.g., `@app.on_event("startup")` or `lifespan` context manager).
   - If `config.PROJECT_FOLDER_TO_INDEX` is set and exists, run `indexer.index_project_folder()` on startup in the background.

3. **MCP Integration (`main.py`)**
   - Import and set up the MCP Server (`mcp.server.fastmcp` or similar).
   - Define tools:
     - `semantic_code_search(query: str, n_results: int = 3)`: Calls `searcher.search()`.
     - `index_folder(folder_path: str)`: Calls `indexer.index_project_folder()`.
   - Start the MCP server.
