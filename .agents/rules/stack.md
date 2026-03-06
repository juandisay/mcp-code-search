---
trigger: always_on
glob:
description: Project technology stack and coding standards
---

# Technology Stack

- **Language:** Python 3.10+
- **MCP SDK:** `mcp >= 0.1.0` (Anthropic)
- **API Framework:** FastAPI + Uvicorn
- **Vector Database:** ChromaDB (persistent, local)
- **Embedding Model:** `all-MiniLM-L6-v2` via
  `sentence-transformers`
- **Text Splitting:** `langchain-text-splitters`
  (language-aware chunking)
- **Config:** `pydantic-settings` + `.env`
- **Testing:** `pytest` (tests live in `tests/`)
- **Linting:** `flake8` with PEP 8, max line length 80

# Coding Standards

- Follow **PEP 8** strictly
- Max line length: **80 characters**
- Use `flake8` for linting
- All tests go in the `tests/` directory
- Use `pytest` as the test runner
- Activate venv before any command:
  `source venv/bin/activate`
- Type hints on all public function signatures
- Docstrings on all public classes and functions

# Project Structure

```
mcp-code-search/
├── main.py           # Entry point (FastAPI + MCP)
├── config.py         # pydantic-settings config
├── core/
│   ├── indexer.py    # Chunking & ChromaDB indexing
│   └── searcher.py   # Semantic search queries
├── tests/            # All pytest tests
├── data/             # ChromaDB persistent storage
├── skills.md         # Capabilities catalog
└── requirements.txt
```

# Dependencies

See `requirements.txt` for the full list:

```
mcp>=0.1.0
fastapi
uvicorn
chromadb
sentence-transformers
langchain-text-splitters
pydantic
python-dotenv
pydantic-settings
```

Dev dependencies (install manually):

```
pytest
flake8
```
