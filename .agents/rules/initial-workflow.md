# Initial Workflow & Context Rules (MANDATORY)

## 🚫 No Direct Project Analysis
- **DO NOT** analyze the project by manually listing directories or reading multiple files to "understand the project logic" directly.
- You MUST leverage the `code-memory` MCP for project understanding.
- **Noise Filtering**: Ignore `node_modules`, `.git`, `dist`, `build` during any interaction.

## 🛠️ Performance & Memory
- **REAL-TIME WATCHER**: There is an automatic filesystem watcher running in the background. You **DO NOT** need to re-trigger `index_folder` manually after creating or modifying code; the server incrementally indexes changes automatically.
- **Mandatory Indexing**: Call `mcp_code-memory_index_folder` at the very start of every new session to ensure the "Brain" is up-to-date.
- **Post-Action Indexing**: Always re-index the project after creating or modifying code files to maintain sync.
- **Brain Mode**: Treat `code-memory` as the primary source of truth for project structure and logic. Avoid manual directory exploration unless semantic search fails.

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


<!-- MAHAGURU_AI_CASCADING_START -->
## 🛸 AI Cascading & Planning (MANDATORY)
- **Mahaguru Planning First**: Every complex task (logic/architectural) MUST start with a Mahaguru-approved plan.
- **Worker Execution**: The Worker (Flash) executes based on the Mahaguru's plan.
- **3-Strike Rule**: If the Worker fails 3 times, call `request_mahaguru_refinement` for a micro-response.
- **Micro-Suggestions**: The Worker may suggest completions or optimizations during the planning phase.
<!-- MAHAGURU_AI_CASCADING_END -->