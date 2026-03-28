# Code-Memory MCP

> **Semantic code search for your local repositories, powered by ChromaDB, AST-based chunking, and AI Cascading.**
>
> Find functions, classes, and logic across your codebase using natural language — 100% local, accurate, and resilient.

---

## ✨ Key Features

- 🔍 **Two-Stage Semantic Search** — Initial retrieval via ChromaDB followed by **Cross-Encoder Reranking** for superior accuracy.
- 📦 **AST-based Smart Chunking** — Language-aware splitting (Python, JS, TS, Go, Java, Markdown) that preserves functional context.
- 🔄 **Real-time File Watcher** — Automatically re-indexes changed files to keep your "memory" always fresh.
- 🎓 **AI Cascading (Mahaguru)** — Escalate complex tasks to high-level planner models with automatic RAG context.
- 🔌 **MCP Protocol** — Native integration as an MCP server for Claude Desktop, Cursor, Antigravity, and more.
- 🔒 **Privacy First** — 100% local processing; no code leaves your machine for indexing or search.

---

## 📚 Documentation

For detailed information, please refer to the following guides:

- 🏗️ **[Architecture & Concepts](docs/architecture.md)** — Deep dive into how the system works (AST chunking, Reranking, Data flows).
- 🛠️ **[MCP Tools Reference](docs/mcp_tools.md)** — Full guide for AI agents interacting with the server.
- 🔌 **[API Reference](docs/api_reference.md)** — Documentation for the FastAPI management endpoints.
- 🚀 **[User Guide & Setup](docs/user_guide.md)** — Installation, configuration, and operational instructions.
- 📝 **[Original PRD](docs/prd.md)** — The initial design and requirements document.

---

## 🚀 Quick Start

### 1. Install
```bash
git clone <your-repo-url> mcp-code-search
cd mcp-code-search
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure
Copy `.env.example` to `.env` and set your paths and keys.

### 3. Run
**Mode A: Management API**
```bash
python main.py
```

**Mode B: MCP Server (for AI Clients)**
```bash
python main.py --mcp
```

**Mode C: Manual Indexing**
```bash
python main.py --index /path/to/project
```

---

## 🔌 IDE & Client Integration

### Claude Desktop

Edit your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "code-memory": {
      "command": "/absolute/path/to/mcp-code-search/run_mcp.sh",
      "args": [],
      "env": {
        "PROJECT_FOLDER_TO_INDEX": "/path/to/your/project"
      }
    }
  }
}
```

### Antigravity & Cursor

Untuk memasang di Antigravity atau Cursor, cukup tambahkan config berikut di pengaturan MCP:

```json
{
  "mcpServers": {
    "code-memory": {
      "command": "/absolute/path/to/mcp-code-search/run_mcp.sh"
    }
  }
}
```

> [!TIP]
> Menggunakan `run_mcp.sh` lebih direkomendasikan karena ia secara otomatis menangani variabel lingkungan yang diperlukan untuk stabilitas sistem.

---

## 📁 Project Structure


```
mcp-code-search/
├── main.py              # Entry point (FastAPI + MCP)
├── core/                # Core logic (Indexer, Searcher, Watcher, etc.)
├── data/                # Persistent storage (auto-created)
├── docs/                # Detailed documentation suite
├── tests/               # Unit and integration tests
├── .env.example         # Environment template
└── requirements.txt     # Dependencies
```

---

## 📄 License
MIT
