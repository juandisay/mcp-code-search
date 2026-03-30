import logging
from typing import Any, Dict, List

import tree_sitter
import tree_sitter_c
import tree_sitter_c_sharp
import tree_sitter_cpp
import tree_sitter_css
import tree_sitter_go
import tree_sitter_html
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_php
import tree_sitter_python
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_typescript
from langchain_text_splitters import RecursiveCharacterTextSplitter

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

    # Keywords in node types that represent imports across common languages
    IMPORT_NODE_TYPES = [
        'import_statement', 'import_from_statement', # Python
        'import_declaration', # JS, TS, Go, Java
        'use_declaration', # Rust
        'using_directive', # C#
        'include_directive', # C, C++
    ]

    # Node types that represent a class across languages
    CLASS_NODE_TYPES = [
        'class_definition', # Python
        'class_declaration', # JS, TS, Java
        'struct_specifier', # C, C++, Rust
        'struct_type', # Go
        'interface_declaration', # TS, Java
    ]

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
        """Backward compatibility: split text and return chunks only."""
        chunks_data = self.split_with_metadata(text)
        return [c["text"] for c in chunks_data]

    def split_with_metadata(self, text: str) -> List[Dict[str, Any]]:
        """Split text and return chunks with associated AST metadata."""
        if not self.parser:
            return [{"text": c, "metadata": {}} for c in self.fallback_splitter.split_text(text)]

        text_bytes = text.encode('utf-8')
        try:
            tree = self.parser.parse(text_bytes)
        except Exception as e:
            logger.warning(f"AST parsing failed for {self.extension}: {e}")
            return [{"text": c, "metadata": {}} for c in self.fallback_splitter.split_text(text)]

        # 1. Extract all imports in the file
        file_imports = []
        def find_imports(node):
            if node.type in self.IMPORT_NODE_TYPES:
                file_imports.append(text_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='replace').strip())
            for child in node.children:
                find_imports(child)
        find_imports(tree.root_node)
        
        # Deduplicate and limit imports to avoid metadata bloat
        unique_imports = sorted(list(set(file_imports)))
        imports_str = "\n".join(unique_imports)
        if len(imports_str) > 1500:
            imports_str = imports_str[:1500] + "... (truncated)"

        # 2. Collect logical blocks
        nodes_collected = []
        
        def get_hierarchy(node):
            if not node:
                return []
            hierarchy = []
            current = node.parent
            while current:
                if current.type in self.CLASS_NODE_TYPES:
                    # Extract class name if possible
                    name_node = current.child_by_field_name('name')
                    if not name_node:
                        # Fallback for languages where name might not be a field
                        for child in current.children:
                            if child.type in ['identifier', 'type_identifier']:
                                name_node = child
                                break
                    
                    if name_node:
                        name = text_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8', errors='replace')
                        hierarchy.append(name)
                current = current.parent
            return hierarchy[::-1]

        def collect_nodes(node):
            node_type = node.type.lower()
            
            # If it's a function/method/interface member, collect it
            is_func = any(kw in node_type for kw in ['function', 'method'])
            is_other = any(kw in node_type for kw in ['struct', 'interface']) and not any(kw in node_type for kw in ['class'])

            if is_func or is_other:
                nodes_collected.append({
                    "range": (node.start_byte, node.end_byte),
                    "class_hierarchy": get_hierarchy(node)
                })
                return # Don't go deeper into functions
            
            # If it's a class, we traverse its children to find methods
            if any(kw in node_type for kw in ['class']):
                for child in node.children:
                    collect_nodes(child)
                return

            # Otherwise, keep looking
            for child in node.children:
                collect_nodes(child)

        collect_nodes(tree.root_node)
        nodes_collected.sort(key=lambda x: x["range"][0])

        final_chunks = []
        current_byte = 0

        for node_data in nodes_collected:
            start_byte, end_byte = node_data["range"]
            hierarchy = node_data["class_hierarchy"]

            # Gap before this node
            if start_byte > current_byte:
                gap_text = text_bytes[current_byte:start_byte].decode('utf-8', errors='replace').strip()
                if gap_text:
                    # Find hierarchy for the gap by checking the node at the start of the gap
                    try:
                        gap_node = tree.root_node.descendant_for_byte_range(current_byte, current_byte + 1)
                        gap_hierarchy = get_hierarchy(gap_node)
                    except Exception:
                        gap_hierarchy = []
                        
                    for c in self.fallback_splitter.split_text(gap_text):
                        final_chunks.append({"text": c, "metadata": {"imports": imports_str, "class_hierarchy": gap_hierarchy}})

            # The logical block
            chunk_text = text_bytes[start_byte:end_byte].decode('utf-8', errors='replace').strip()
            if chunk_text:
                if len(chunk_text) > self.chunk_size:
                    for c in self.fallback_splitter.split_text(chunk_text):
                        final_chunks.append({"text": c, "metadata": {"imports": imports_str, "class_hierarchy": hierarchy}})
                else:
                    final_chunks.append({"text": chunk_text, "metadata": {"imports": imports_str, "class_hierarchy": hierarchy}})

            current_byte = max(current_byte, end_byte)

        # Remaining bytes
        if current_byte < len(text_bytes):
            gap_text = text_bytes[current_byte:].decode('utf-8', errors='replace').strip()
            if gap_text:
                for c in self.fallback_splitter.split_text(gap_text):
                    final_chunks.append({"text": c, "metadata": {"imports": imports_str}})

        if not final_chunks:
            return [{"text": c, "metadata": {"imports": imports_str}} for c in self.fallback_splitter.split_text(text)]

        return final_chunks
