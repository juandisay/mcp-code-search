import logging
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
import tree_sitter
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript
import tree_sitter_go
import tree_sitter_java
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_php
import tree_sitter_c
import tree_sitter_cpp
import tree_sitter_c_sharp
import tree_sitter_html
import tree_sitter_css

logger = logging.getLogger(__name__)

EXTENSION_TO_TS_LANG = {
    ".py": tree_sitter.Language(tree_sitter_python.language()),
    ".js": tree_sitter.Language(tree_sitter_javascript.language()),
    ".jsx": tree_sitter.Language(tree_sitter_javascript.language()),
    ".ts": tree_sitter.Language(tree_sitter_typescript.language_typescript()),
    ".tsx": tree_sitter.Language(tree_sitter_typescript.language_tsx()),
    ".go": tree_sitter.Language(tree_sitter_go.language()),
    ".java": tree_sitter.Language(tree_sitter_java.language()),
    ".rb": tree_sitter.Language(tree_sitter_ruby.language()),
    ".rs": tree_sitter.Language(tree_sitter_rust.language()),
    ".php": tree_sitter.Language(tree_sitter_php.language_php()),
    ".c": tree_sitter.Language(tree_sitter_c.language()),
    ".cpp": tree_sitter.Language(tree_sitter_cpp.language()),
    ".cs": tree_sitter.Language(tree_sitter_c_sharp.language()),
    ".html": tree_sitter.Language(tree_sitter_html.language()),
    ".css": tree_sitter.Language(tree_sitter_css.language()),
}

class ASTChunker:
    """Chunks code files using Tree-sitter AST to preserve logical boundaries."""

    # Keywords in node types that usually represent logical code blocks
    CHUNKABLE_KEYWORDS = ['function', 'class', 'method', 'struct', 'interface']

    def __init__(
        self,
        chunk_size: int,
        chunk_overlap: int,
        extension: str
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.extension = extension
        
        self.ts_lang = EXTENSION_TO_TS_LANG.get(extension)
        if self.ts_lang:
            self.parser = tree_sitter.Parser(self.ts_lang)
        else:
            self.parser = None

        # Fallback splitter for unhandled text or huge nodes
        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            is_separator_regex=False
        )

    def split_text(self, text: str) -> List[str]:
        if not self.parser:
            return self.fallback_splitter.split_text(text)

        text_bytes = text.encode('utf-8')
        try:
            tree = self.parser.parse(text_bytes)
        except Exception as e:
            logger.warning(f"AST parsing failed for {self.extension}: {e}")
            return self.fallback_splitter.split_text(text)

        nodes_collected = []
        def collect_nodes(node):
            node_type = node.type.lower()
            if any(kw in node_type for kw in self.CHUNKABLE_KEYWORDS):
                nodes_collected.append((node.start_byte, node.end_byte))
                return # Don't go deeper to preserve the class/function as a whole block
            for child in node.children:
                collect_nodes(child)

        collect_nodes(tree.root_node)
        nodes_collected.sort()

        final_chunks = []
        current_byte = 0

        for start_byte, end_byte in nodes_collected:
            # Check for generic gap before this node
            if start_byte > current_byte:
                gap_bytes = text_bytes[current_byte:start_byte]
                gap_text = gap_bytes.decode('utf-8', errors='replace').strip()
                if gap_text:
                    final_chunks.extend(self.fallback_splitter.split_text(gap_text))
            
            # The logical block
            chunk_bytes = text_bytes[start_byte:end_byte]
            chunk_text = chunk_bytes.decode('utf-8', errors='replace').strip()
            
            if chunk_text:
                if len(chunk_text) > self.chunk_size:
                    # Block is too large, fallback split just this block
                    final_chunks.extend(self.fallback_splitter.split_text(chunk_text))
                else:
                    final_chunks.append(chunk_text)
            
            current_byte = max(current_byte, end_byte)

        # Remaining bytes
        if current_byte < len(text_bytes):
            gap_bytes = text_bytes[current_byte:]
            gap_text = gap_bytes.decode('utf-8', errors='replace').strip()
            if gap_text:
                final_chunks.extend(self.fallback_splitter.split_text(gap_text))

        if not final_chunks:
            return self.fallback_splitter.split_text(text)

        return final_chunks
