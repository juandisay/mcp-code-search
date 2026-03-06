# Phase 2: Core Engine (Indexer & Searcher)

## Objective

Implement the logic to index local code files into ChromaDB and query them.

## Tasks

1. **Indexer (`core/indexer.py`)**
   - `CodeIndexer` class managing a ChromaDB collection (`code_snippets`).
   - Implement `index_project_folder(folder_path)`:
     - Traverse the given folder path recursively.
     - Include files with extensions: `.py`, `.js`, `.ts`, `.go`, `.java`, `.md`.
     - Exclude directories: `node_modules`, `.git`, `venv`, `__pycache__`.
   - Read file content and chunk it.
     - Use LangChain's `RecursiveCharacterTextSplitter` or Language-specific splitters.
   - Insert chunks into ChromaDB with metadata (`file_path`, `start_line`, `project_name`).

2. **Searcher (`core/searcher.py`)**
   - `CodeSearcher` class that connects to the same ChromaDB collection.
   - Implement `search(query, n_results=3)`:
     - Query the vector database for the top `n_results` matching the natural language `query`.
     - Return structured results including the snippet, `file_path`, and `start_line`.
