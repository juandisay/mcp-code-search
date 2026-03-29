import os

from config import config
from core.context_assembler import ContextAssembler


def test_is_path_safe_allowed():
    """Verify that project files are considered safe."""
    # Test with a file that should exist in the project
    safe_path = os.path.join(config.PROJECT_ROOT, "main.py")
    assert ContextAssembler.is_path_safe(safe_path) is True

def test_is_path_safe_blocked():
    """Verify that files outside the project root are blocked."""
    # Test with a sensitive system path
    unsafe_path = "/etc/passwd"
    assert ContextAssembler.is_path_safe(unsafe_path) is False

    # Test with path traversal attempts
    traversal_path = os.path.join(config.PROJECT_ROOT, "..", "..", "etc", "passwd")
    assert ContextAssembler.is_path_safe(traversal_path) is False

def test_read_file_chunked_limit(tmp_path):
    """Verify that large files are truncated correctly."""
    large_file = tmp_path / "large.txt"
    # Create a file slightly larger than the 100KB limit
    content = "A" * (config.MAX_CONTEXT_FILE_SIZE + 1024)
    large_file.write_text(content)

    read_content = ContextAssembler.read_file_chunked(str(large_file), max_bytes=config.MAX_CONTEXT_FILE_SIZE)

    assert "truncated due to size limit" in read_content
    # Content should be roughly the size of the limit
    assert len(read_content.split("\n")[0]) == config.MAX_CONTEXT_FILE_SIZE

def test_read_file_binary_safety(tmp_path):
    """Verify that binary files don't cause crashes."""
    binary_file = tmp_path / "binary.bin"
    # Write some non-UTF-8 bytes
    binary_file.write_bytes(b"\x80\x81\x82")

    read_content = ContextAssembler.read_file_chunked(str(binary_file))
    assert "Unable to decode" in read_content
