---
description: Development & Indexing Workflow
---

# Development Workflow (MANDATORY)

## 1. Mandatory Project Indexing
// turbo
- **Initial Indexing**: Run the `code-memory:index_folder` tool with the absolute path of the current workspace first.
- **Auto-Update**: After every implementation or modification, you MUST automatically run `code-memory:index_folder` again to update the vector database.

## 2. Mandatory Search & Context
- **No Direct Analysis**: Do not attempt to analyze the project directly without using search.
- **Query Strategy**: Generate at least 2-3 different queries for search: 
  1. Primary logic/feature name.
  2. Related unit tests or examples.
  3. Similar patterns or reusable components in other modules.
- **Search First**: Before editing or proposing code, you MUST perform a semantic search to understand existing patterns and logic.
  `code-memory:semantic_code_search(query="<multi_perspective_query>")`

## 3. Planning & Documentation
- **Pre-check Skills**: Scan `.agents/skills/` for existing helpers before planning.
- Create a mature implementation plan before writing any code.
- Ensure every logic block has its documentation.

## 4. Implementation & Validation
- **Code Implementation**: Write the code following the plan.
- **Post-Implementation RAG**: After writing, perform a search on the NEW code to ensure it aligns semantically with the project standards.
- **Final Sync**: Perform a final `index_folder` call.

## 5. Skills Capture
- If a feature is identified as "usable", create a new skill in `.agents/skills/`.

