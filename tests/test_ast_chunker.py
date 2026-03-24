"""Tests for core.ast_chunker module."""
import pytest
from core.ast_chunker import ASTChunker, EXTENSION_TO_TS_LANG

class TestASTChunker:
    """Tests for the ASTChunker class."""

    def test_init_supported_extension(self):
        """ASTChunker initializes correctly with supported extension."""
        chunker = ASTChunker(chunk_size=1000, chunk_overlap=200, extension=".py")
        assert chunker.parser is not None
        assert chunker.ts_lang == EXTENSION_TO_TS_LANG[".py"]

    def test_init_unsupported_extension(self):
        """ASTChunker falls back to generic splitter for unknown extensions."""
        chunker = ASTChunker(chunk_size=1000, chunk_overlap=200, extension=".unknown")
        assert chunker.parser is None

    def test_chunking_python_functions(self):
        """ASTChunker splits python code by function correctly."""
        code = '''
def first_function():
    print("hello from first")

class MyClass:
    def method_one(self):
        pass

def second_function():
    return 42
'''
        chunker = ASTChunker(chunk_size=1000, chunk_overlap=0, extension=".py")
        chunks = chunker.split_text(code)
        
        assert len(chunks) == 3
        assert 'def first_function():' in chunks[0]
        assert 'class MyClass:' in chunks[1]
        assert 'def method_one(self):' in chunks[1]
        assert 'def second_function():' in chunks[2]

    def test_fallback_on_large_chunk(self):
        """ASTChunker splits a single large node using fallback splitter."""
        long_func_body = "    print('a')\n" * 50
        code = f"def huge_function():\n{long_func_body}"
        
        chunker = ASTChunker(chunk_size=100, chunk_overlap=10, extension=".py")
        chunks = chunker.split_text(code)
        
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 100

    def test_gap_chunking(self):
        """ASTChunker keeps code gaps (e.g. imports) properly."""
        code = '''
import os
import sys

def foo():
    pass

x = 100
y = 200
'''
        chunker = ASTChunker(chunk_size=1000, chunk_overlap=0, extension=".py")
        chunks = chunker.split_text(code)
        
        assert len(chunks) == 3
        assert 'import os' in chunks[0]
        assert 'def foo():' in chunks[1]
        assert 'x = 100' in chunks[2]
