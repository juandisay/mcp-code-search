# Phase 1: Setup & Configuration

## Objective

Set up the foundational project structure, dependencies, and configuration.

## Tasks

1. **Define Dependencies**
   - Create `requirements.txt` containing:
     - `mcp>=0.1.0`
     - `fastapi`
     - `uvicorn`
     - `chromadb`
     - `sentence-transformers`
     - `langchain-text-splitters`
     - `pydantic`
     - `python-dotenv`
     - `pydantic-settings`

2. **Configuration Module**
   - Create `config.py` using `pydantic-settings` to load environment variables from `.env`.
   - Variables needed:
     - `CHROMA_DATA_PATH`: default `"data"`
     - `PROJECT_FOLDER_TO_INDEX`: default `""` (Path to auto-index on startup)

3. **Environment setup**
   - Create `.env.example` file based on `config.py` structure.
