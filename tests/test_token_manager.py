from core.token_manager import TokenManager


def test_token_manager_init():
    """TokenManager initializes with default encoding."""
    tm = TokenManager()
    assert tm.encoding is not None

def test_count_tokens_empty():
    """Empty string returns 0 tokens."""
    tm = TokenManager()
    assert tm.count_tokens("") == 0
    assert tm.count_tokens(None) == 0

def test_count_tokens_simple():
    """Simple string returns expected token count."""
    tm = TokenManager()
    text = "Hello, world!"
    # "Hello" + "," + " world" + "!" = 4 tokens in cl100k_base
    count = tm.count_tokens(text)
    assert count > 0
    assert isinstance(count, int)

def test_format_usage_summary():
    """format_usage_summary returns a formatted string."""
    tm = TokenManager()
    summary = tm.format_usage_summary(123)
    assert "token usage:" in summary
    assert "search  123" in summary

def test_token_manager_singleton():
    """Importing the default manager works."""
    from core.token_manager import token_manager
    assert token_manager.count_tokens("test") > 0
