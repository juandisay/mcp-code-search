---
description: Development & Indexing Workflow
---

# Development Workflow (MANDATORY)

## 1. Managed Indexing
- **Automatic Sync**: The system watches for file changes. Do NOT manually call `index_folder` during implementation unless the automatic watcher fails.

## 2. Optimized Search & Context
- **Selective Search**: Perform semantic search to understand existing patterns before editing.
- **Query Strategy**: Generate a single, high-quality multi-perspective query instead of multiple redundant ones:
  - `code-memory:semantic_code_search(query="<logic_and_related_patterns>")`
- **Context Management**: Only read what is necessary. Avoid re-searching for things already cached in the conversation history.

## 3. Planning & Documentation
- Pre-check `.agents/skills/` to reuse existing helpers.
- Create a concise implementation plan before writing code.
- Ensure only necessary logic gets deep documentation to keep files lean.

## 4. Implementation & Validation
- **Code Implementation**: Follow the plan.
- **Verification**: If complex, perform a quick search on the new code to ensure it matches project standards.

## 5. Skills Capture
- If a feature is identified as "usable", create a new skill in `.agents/skills/`.

## 6. Usage Awareness
- Be mindful of context size. Avoid long output snippets when not requested.
- **Token Summary**: Append usage summary as specified in `core/token_manager.py`:
  
  token usage:
  search  <total_search_tokens_used>
  llm usage <estimated_llm_tokens_used>


