# Customize Antigravity with Code-Memory

This project is configured to use **Antigravity** with enhanced RAG (Retrieval-Augmented Generation) capabilities via the `code-memory` MCP.

## Activation Steps

To enable the automated indexing and skill management, you can run this one-liner:

```bash
find .agents -name "*.template" -exec sh -c 'mv "$1" "${1%.template}"' _ {} \;
```

Or manually rename the following files:

## How It Works

1. **Auto-Indexing**: Every time a new prompt session begins, the agent will call `code-memory:index_folder` to ensure the vector database knows your latest code.
2. **Dynamic Stack Detection**: The agent will automatically scan your files (like `package.json`, `requirements.txt`) to identify the languages and frameworks used, then adapt its rules accordingly.
3. **Context-First**: The agent is instructed to perform a `semantic_code_search` before making any suggestions.
3. **Skill Capture**: Reusable logic is automatically saved to `.agents/skills/` when marked as "usable".
4. **Planning & Docs**: Every change requires a formal plan and detailed documentation.

## Running the Setup

The `code-memory` MCP server will automatically handle the context management once these files are activated. Make sure your local environment has the `code-memory` MCP server configured.
