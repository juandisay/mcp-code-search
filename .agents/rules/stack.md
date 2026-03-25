# Project Technology Stack (Python / FastAPI / ChromaDB)

## 🐍 Python Environment & Libraries
- **Language**: Python 3.10+
- **Project Root**: `/Users/juandisay/Organizer/mcp-code-search`
- **Core Dependencies**:
  - `fastapi` & `uvicorn`: Digunakan di `main.py` untuk management API.
  - `mcp` (FastMCP): Digunakan untuk implementasi Model Context Protocol server.
  - `chromadb`: Vector database untuk penyimpanan index kode (lokal di folder `data/`).
  - `sentence-transformers`: Digunakan untuk menghasilkan embedding dari potongan kode.
  - `pydantic` & `pydantic-settings`: Digunakan di `config.py` dan data model untuk validasi dan manajemen konfigurasi.
  - `langchain-text-splitters`: Digunakan di `core/indexer.py` untuk memecah file kode menjadi bagian-bagian kecil (chunks).

## 📂 Critical Project Paths (Absolute)
- **Entry Point**: `/Users/juandisay/Organizer/mcp-code-search/main.py`
- **Core Logic**: `/Users/juandisay/Organizer/mcp-code-search/core/`
  - Indexer: `core/indexer.py`
  - Searcher: `core/searcher.py`
- **Configuration**: `/Users/juandisay/Organizer/mcp-code-search/config.py`
- **Database Storage**: `/Users/juandisay/Organizer/mcp-code-search/data/`
- **Requirements**: `/Users/juandisay/Organizer/mcp-code-search/requirements.txt`

## 🛠️ Development Standards
- **Linter**: Flake8 (linting rules ada di `.flake8`).
- **Testing**: Pytest (semua test harus ada di folder `tests/`).
- **Environment**: Menggunakan `venv` di root project.

## 📜 Coding Guidelines
- **PEP 8**: Wajib diikuti untuk kebersihan kode Python.
- **Type Hinting**: Gunakan type hints pada setiap fungsi dan variabel.
- **Docstrings**: Setiap class dan function baru wajib memiliki docstring deskriptif.
- **Automatic Sync**: Indexing dikelola otomatis oleh background watcher.


