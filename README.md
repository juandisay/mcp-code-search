# Code-Memory MCP

> **Semantic code search for your local repositories, powered by ChromaDB and MCP.**
>
> Find functions, classes, and logic across your codebase using natural language — 100% local, no tokens wasted.

---

## ✨ Features

- 🔍 **Semantic Search** — Query your code with natural language (e.g. _"upload file to S3"_)
- 📦 **Smart Chunking** — Language-aware splitting for Python, JS, TS, Go, Java, Markdown
- 🗄️ **Persistent Storage** — ChromaDB with `all-MiniLM-L6-v2` embeddings, stored locally
- 🔌 **MCP Protocol** — Plug directly into Claude Desktop, Cursor, Antigravity, Windsurf, and more
- 🚀 **Auto-Index on Startup** — Configure a project folder and it indexes automatically
- 🔒 **Localhost Only** — FastAPI management API only binds to `127.0.0.1`

---

## 📋 Prerequisites

- **Python 3.10+**
- **pip** (or a virtual environment manager)

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <your-repo-url> mcp-code-search
cd mcp-code-search

python -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
CHROMA_DATA_PATH=data
PROJECT_FOLDER_TO_INDEX=/path/to/your/project    # auto-indexes on startup (optional)
```

### 3. Run the Server

There are **two modes** — pick the one you need:

#### Mode A: FastAPI (Management API)

```bash
python main.py
```

Starts on `http://127.0.0.1:8000`. Use this for REST management:

| Endpoint | Method | Description                                           |
| -------- | ------ | ----------------------------------------------------- |
| `/index` | POST   | Index a folder: `{"folder_path": "/path/to/project"}` |
| `/stats` | GET    | View total indexed chunks, collection name            |
| `/docs`  | GET    | Interactive Swagger documentation                     |

#### Mode B: MCP Server (stdio)

```bash
python main.py --mcp
```

Starts the MCP server over **stdio transport** — this is what AI clients connect to.

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
        "CHROMA_DATA_PATH": "data",
        "PROJECT_FOLDER_TO_INDEX": "/path/to/your/project"
      }
    }
  }
}
```

Restart Claude Desktop. The tools `semantic_code_search` and `index_folder` will appear automatically.

---

### Cursor

Open **Settings → MCP** (or `Cmd+Shift+P` → "MCP: Add Server"), then add:

```json
{
  "mcpServers": {
    "code-memory": {
      "command": "/absolute/path/to/mcp-code-search/run_mcp.sh",
      "args": [],
      "env": {
        "CHROMA_DATA_PATH": "data",
        "PROJECT_FOLDER_TO_INDEX": "/path/to/your/project"
      }
    }
  }
}
```

You can also place this in `.cursor/mcp.json` at your project root for per-project config.

---

### Antigravity IDE (Google)

Edit your Antigravity settings file:

- **macOS**: `~/.gemini/settings.json`

```json
{
  "mcpServers": {
    "code-memory": {
      "command": "/absolute/path/to/mcp-code-search/run_mcp.sh",
      "args": [],
      "env": {
        "CHROMA_DATA_PATH": "data",
        "PROJECT_FOLDER_TO_INDEX": "/path/to/your/project"
      }
    }
  }
}
```

---

### Windsurf

Add to your Windsurf MCP configuration (`~/.windsurf/mcp.json` or via Settings):

```json
{
  "mcpServers": {
    "code-memory": {
      "command": "/absolute/path/to/mcp-code-search/run_mcp.sh",
      "args": []
    }
  }
}
```

---

### VS Code (Copilot MCP / Roo Code)

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "code-memory": {
      "type": "stdio",
      "command": "/absolute/path/to/mcp-code-search/run_mcp.sh",
      "args": []
    }
  }
}
```

---

### MCP Inspector (Testing & Debugging)

Use the official MCP dev tool to inspect and test your tools:

```bash
npx @modelcontextprotocol/inspector
```

Then connect to:

```
Command: /absolute/path/to/run_mcp.sh
Args:    
```

---

## 🛠️ MCP Tools Reference

Once connected, AI clients can call these tools:

### `semantic_code_search`

Search for code snippets using natural language.

| Parameter            | Type           | Required | Default | Description                                                  |
| -------------------- | -------------- | -------- | ------- | ------------------------------------------------------------ |
| `query`              | string         | ✅       | —       | Natural language query, e.g. _"function that uploads to S3"_ |
| `n_results`          | integer        | —        | `3`     | Number of results to return                                  |
| `project_name`       | string         | —        | `null`  | Filter results by project name                               |
| `max_distance`       | float          | —        | `null`  | Override relevance threshold (lower = stricter)              |
| `language`           | list\[string\] | —        | `null`  | Filter by file extension(s), e.g. `[".py", ".ts"]`          |
| `file_path_includes` | string         | —        | `null`  | Only return results whose path contains this substring       |
| `excluded_dirs`      | list\[string\] | —        | `null`  | Exclude results from these directories, e.g. `["tests"]`     |

### `index_folder`

Index a local project folder into the database.

| Parameter     | Type   | Required | Description                         |
| ------------- | ------ | -------- | ----------------------------------- |
| `folder_path` | string | ✅       | Absolute path to the project folder |

---

## 💡 How to Trigger the Tools

Once you've connected the MCP server to your AI client (see [IDE & Client Integration](#-ide--client-integration) above), there are several ways to trigger the tools.

### From an AI Client (Natural Language)

Simply ask your AI assistant in natural language. It will automatically call the right MCP tool:

```text
# Searching for code
"Find the function that handles user authentication"
"Show me code related to database migrations"
"Where is the S3 upload logic?"

# Indexing a new project
"Index my project at /Users/me/projects/my-app"
"Add /home/user/repos/backend to the code search database"
```

### Direct Tool Calls (JSON)

If your client supports explicit tool invocation, you can call the tools directly:

#### `semantic_code_search`

```json
{
  "tool": "semantic_code_search",
  "arguments": {
    "query": "function that uploads files to S3",
    "n_results": 5,
    "project_name": "my-backend",
    "language": [".py"],
    "file_path_includes": "/core",
    "excluded_dirs": ["tests", "vendor"]
  }
}
```

**Example response:**

```text
--- Result 1 (distance: 0.3241) ---
File: /projects/my-backend/services/storage.py (Line 42)
Project: my-backend
Code:
def upload_to_s3(file_path: str, bucket: str) -> str:
    """Upload a local file to an S3 bucket and return the URL."""
    ...
```

#### `index_folder`

```json
{
  "tool": "index_folder",
  "arguments": {
    "folder_path": "/absolute/path/to/your/project"
  }
}
```

**Example response:**

```text
Successfully indexed folder: /absolute/path/to/your/project
Files processed: 47, Chunks upserted: 312
```

### Via FastAPI REST API

When running in FastAPI mode (`python main.py`), use `curl` or any HTTP client:

#### Index a folder

```bash
curl -X POST http://127.0.0.1:8000/index \
  -H "Content-Type: application/json" \
  -d '{"folder_path": "/absolute/path/to/your/project"}'
```

#### Check stats

```bash
curl http://127.0.0.1:8000/stats
```

**Example response:**

```json
{
  "total_indexed_chunks": 312,
  "collection_name": "code_snippets",
  "chroma_data_path": "data"
}
```

#### Interactive docs

Open `http://127.0.0.1:8000/docs` in your browser for the Swagger UI.

### Via MCP Inspector (Debugging)

```bash
npx @modelcontextprotocol/inspector
```

1. Set **Command** to your venv Python path: `/absolute/path/to/venv/bin/python`
2. Set **Args** to: `/absolute/path/to/main.py --mcp`
3. Click **Connect**
4. Browse the **Tools** tab → select `semantic_code_search` or `index_folder`
5. Fill in the parameters and click **Run**

---

## 📁 Project Structure

```
mcp-code-search/
├── main.py              # Entry point (FastAPI + MCP)
├── config.py            # Environment configuration (pydantic-settings)
├── core/
│   ├── indexer.py       # Code chunking & ChromaDB indexing
│   ├── searcher.py      # Semantic search with metadata filtering
│   ├── ast_chunker.py   # AST-aware code chunking via Tree-sitter
│   ├── watcher.py       # Real-time file watcher (watchdog)
│   ├── token_manager.py # Token usage tracking
│   └── rule_manager.py  # Agent rules sync
├── data/                # ChromaDB persistent storage (auto-created)
├── tests/
│   ├── test_searcher.py # Searcher unit tests
│   └── test_main.py     # MCP tool tests
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
└── docs/
    ├── prd.md           # Product Requirements Document
    └── plan/            # Implementation plan phases
```

---

## 🧪 Testing

```bash
# Run core engine tests
python test_core.py

# Start FastAPI and test endpoints
python main.py &
curl http://127.0.0.1:8000/stats
curl -X POST http://127.0.0.1:8000/index \
  -H "Content-Type: application/json" \
  -d '{"folder_path": "/path/to/project"}'
```

---

## 📄 License

MIT
