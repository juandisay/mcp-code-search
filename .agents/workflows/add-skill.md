---
description: Update skills.md whenever MCP tools, endpoints, or core modules change
---

# Add / Update Skill

Run this workflow whenever any of the following change:

- MCP tools in `main.py` (added, removed, or modified)
- FastAPI endpoints in `main.py`
- Core modules (`core/indexer.py`, `core/searcher.py`)
- Configuration settings in `config.py`
- Supported file extensions or excluded directories

## Steps

1. **Read current `skills.md`** to understand what is
   already documented.

2. **Identify what changed** by reviewing the modified
   source files (`main.py`, `config.py`,
   `core/indexer.py`, `core/searcher.py`).

3. **Update the relevant section(s)** in `skills.md`:
   - **Module Map** — if a new module was added or a
     module's role changed.
   - **MCP Tools** — if a tool was added, removed, or
     its parameters changed. Include name, parameters
     table (type, required, default, description), and
     a brief description.
   - **FastAPI Endpoints** — if an endpoint was added
     or modified.
   - **Supported Languages** — if new file extensions
     were added.
   - **Configuration** — if new env vars were added or
     defaults changed.
   - **Architecture Pipeline** — if the indexing or
     search flow changed.
   - **Optimization Tips** — if new tuning options
     were introduced.
   - **Troubleshooting** — if new known issues or
     solutions were discovered.

4. **Verify** that `skills.md` is valid Markdown and
   all tables render correctly.

5. **Commit** the updated `skills.md` alongside the
   code changes.
