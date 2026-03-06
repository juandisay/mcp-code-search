# Code-Memory MCP Plan

This directory contains the breakdown of the implementation plan for the Code-Memory MCP server.
It is divided into 4 sequential phases:

1. [Phase 1: Setup & Configuration](01_setup_and_config.md)
   - Defines dependencies (`requirements.txt`)
   - Establish `.env` and `config.py` for variables like `PROJECT_FOLDER_TO_INDEX` (to auto-index on startup).
2. [Phase 2: Core Engine](02_core_engine.md)
   - Implement `core/indexer.py` (chunking, smart file splitting).
   - Implement `core/searcher.py` (ChromaDB query logic).
3. [Phase 3: APIs and MCP Integration](03_api_and_mcp.md)
   - `main.py` FastAPI app.
   - MCP endpoints and tools (`semantic_code_search`, `index_folder`).
   - Server lifecycle auto-index process.
4. [Phase 4: Testing & Verification](04_testing_and_verification.md)
   - Manual tests using dummy data and `mcp dev`.
