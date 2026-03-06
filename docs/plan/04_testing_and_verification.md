# Phase 4: Testing & Verification

## Objective

Verify the application works end-to-end as specified in the PRD.

## Tasks

1. **Mock Data**
   - Create a small dummy project with a few Python/JS files to test indexing.

2. **Manual API Testing**
   - Start the FastAPI server (`uvicorn main:app --reload` or via the MCP cli dev mode).
   - Call `GET /stats` to ensure DB is initialized (should be 0).
   - Verify that auto-index on startup works if `.env` is set.
   - Trigger `POST /index` and wait for completion.
   - Call `GET /stats` to verify chunks are inserted.

3. **MCP Interface Testing**
   - Since we are building an MCP server, verify the tools `semantic_code_search` and `index_folder` are properly exposed.
   - Use an MCP client (such as Claude Desktop or `mcp dev`) to invoke `semantic_code_search("dummy query")` and ensure it returns expected snippets.
