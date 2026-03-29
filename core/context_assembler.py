import os
import logging
from config import config
from core.dependencies import get_searcher, get_indexer
from core.token_manager import token_manager

logger = logging.getLogger(__name__)

class ContextAssembler:
    """Facade for gathering and sanitizing context for LLM reasoning."""

    @staticmethod
    def is_path_safe(file_path: str) -> bool:
        """Dynamic security check to ensure path is within an indexed project root."""
        abs_path = os.path.abspath(file_path)
        
        # 1. Static Allowed Roots (Sandboxing)
        allowed_roots = [os.path.abspath(r) for r in config.ALLOWED_CONTEXT_ROOTS]
        if any(abs_path.startswith(root) for root in allowed_roots):
            return True
            
        # 2. Dynamic Indexed Roots (Project-based)
        try:
            indexer = get_indexer()
            indexed_roots = indexer.get_indexed_roots()
            if any(abs_path.startswith(os.path.abspath(root)) for root in indexed_roots):
                return True
        except Exception as e:
            logger.error("Error during dynamic path validation: %s", e)
            
        return False

    @staticmethod
    def read_file_chunked(file_path: str, max_bytes: int = 1048576) -> str:
        """Read a file up to max_bytes with UTF-8 safety."""
        try:
            with open(file_path, "rb") as f:
                content_bytes = f.read(max_bytes)
                content = content_bytes.decode("utf-8", errors="replace")
                
                if f.peek(1): # Still more data
                    content += "\n\n[... File truncated due to size limit ...]"
                return content
        except UnicodeDecodeError:
            return "[Error: Unable to decode file as UTF-8 text (possibly binary)]"
        except Exception as e:
            return f"[Error reading file: {str(e)}]"

    @staticmethod
    def format_search_results(results: list) -> str:
        """Helper to format search results into a clean string."""
        if not results:
            return "No relevant code snippets found."

        lines = []
        for i, res in enumerate(results):
            dist = res.get("distance")
            dist_info = f" (distance: {dist:.4f})" if dist is not None else ""
            proj = res.get("project_name", "Unknown")
            lines.append(
                f"--- Snippet {i + 1}{dist_info} ---\n"
                f"File: {res['file_path']} (Line {res['start_line']})\n"
                f"Project: {proj}\n"
                f"Code:\n{res['snippet']}\n"
            )
        return "\n".join(lines)

    @classmethod
    def assemble_refinement_context(cls, brief: str, relevant_files: list[str] = None) -> str:
        """Gathers RAG context, reads explicit files, and enforces token limits."""
        # 1. Automatic RAG Context
        rag_context = ""
        try:
            searcher = get_searcher()
            search_results = searcher.search(
                query=brief,
                n_results=config.MAHAGURU_AUTO_CONTEXT_COUNT
            )
            if search_results:
                rag_context = (
                    "### AUTO-RETRIEVED CONTEXT FROM INDEXER\n"
                    "The following snippets were found based on semantic relevance to your request:\n\n"
                    + cls.format_search_results(search_results)
                )
        except Exception as e:
            logger.warning("Failed to auto-retrieve RAG context for Mahaguru: %s", e)

        # 2. Explicit File Context
        file_context = ""
        if relevant_files:
            context_parts = []
            for file_path in relevant_files:
                if not cls.is_path_safe(file_path):
                    logger.warning("Blocked access to unsafe file path: %s", file_path)
                    context_parts.append(f"### File: {file_path}\n[Access Denied: Path outside allowed context roots]")
                    continue

                if os.path.isfile(file_path):
                    content = cls.read_file_chunked(file_path, max_bytes=config.MAX_CONTEXT_FILE_SIZE)
                    context_parts.append(f"### File: {file_path}\n```\n{content}\n```")
                else:
                    context_parts.append(f"### File: {file_path}\n[Error: File not found]")

            file_context = "\n\n".join(context_parts)

        # 3. Combine Context with Token Budgeting
        full_context = ""
        total_tokens = 0

        if rag_context:
            full_context += rag_context + "\n\n"
            total_tokens += token_manager.count_tokens(rag_context)

        if file_context:
            file_tokens = token_manager.count_tokens(file_context)
            if total_tokens + file_tokens > config.MAX_TOTAL_CONTEXT_TOKENS:
                logger.warning("Context exceeds token limit. Truncating file context.")
                full_context += "### (Truncated File Context)\n"
            else:
                full_context += file_context

        return full_context

context_assembler = ContextAssembler()
