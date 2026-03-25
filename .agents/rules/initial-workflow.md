# Initial Workflow & Context Rules (MANDATORY)

## 🚫 No Direct Project Analysis
- **DO NOT** analyze the project by manually listing directories or reading multiple files to "understand the project logic" directly.
- You MUST leverage the `code-memory` MCP for project understanding.
- **Noise Filtering**: Ignore `node_modules`, `.git`, `dist`, `build` during any interaction.

## 🛠️ Automated Indexing
- **Real-time Watcher**: A background filesystem watcher is active. You **DO NOT** need to call `index_folder` manually after creating or modifying code. The server handles incremental updates automatically.
- **Session Start**: Only call `index_folder` at the very start of a NEW chat session if you suspect the index is out of sync.

## 🔍 Context-First Policy (MANDATORY)
- **Targeted Search**: Before planning or proposing changes, use `semantic_code_search` to gather context.
- **Efficiency**: Instead of multiple broad searches, try to combine keywords into 1 or 2 high-quality queries to save context tokens.
- **Dependency Map**: Identify critical imports or reverse dependencies using `grep_search` ONLY when semantic search is insufficient.
- Do not make assumptions. Use code-memory context efficiently.

## 📦 Automated Skill Management
- **Skill Reuse**: Check `.agents/skills/` before creating new logic.
- **Skill Capture**: Save reusable or modular logic to `.agents/skills/[skill-name].md`.

## 📝 Documentation & Planning
- Every task MUST start with a concise implementation plan.
- Every piece of logic MUST be accompanied by documentation.
