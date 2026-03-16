# Initial Workflow & RAG Rules (MANDATORY)

## 🚫 No Direct Project Analysis
- **DO NOT** analyze the project by manually listing directories or reading multiple files to "understand the project logic" directly.
- You MUST leverage the `code-memory` MCP for all project understanding and context gathering.

## 🛠️ Mandatory Indexing
- At the start of every chat session, you **MUST** call the `code-memory` tool `index_folder` with the current project path.
- **AUTOMATIC RE-INDEXING**: After every code implementation, modification, or creation, you **MUST** immediately re-trigger `index_folder` to ensure the vector database is always up-to-date.

## 🔍 Context-First Policy (MANDATORY)
- Before planning any task or proposing changes, you **MUST** use `semantic_code_search` from `code-memory` to gather context about existing implementations.
- Do not make assumptions about the codebase. Context checking through `code-memory` is a mandatory requirement.

## 📦 Automated Skill Management
- When you create logic that is considered "usable" or "modular", save it as a new skill in `.agents/skills/[skill-name].md`.
- Each skill file must include description, implementation details, and reuse instructions.

## 📝 Documentation & Planning
- Every task MUST start with a detailed implementation plan.
- Every piece of logic created MUST be accompanied by comprehensive documentation.
