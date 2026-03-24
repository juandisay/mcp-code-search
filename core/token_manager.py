import tiktoken
import logging

logger = logging.getLogger(__name__)

class TokenManager:
    """Manages token counting for the MCP server."""

    def __init__(self, model_name: str = "gpt-4o"):
        """Initialize TokenManager.
        
        Args:
            model_name: The model to use for encoding (default: gpt-4o).
        """
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except Exception:
            # Fallback to cl100k_base (standard for gpt-4, gpt-3.5)
            self.encoding = tiktoken.get_encoding("cl100k_base")
            logger.warning(
                "Could not find encoding for model %s. Using cl100k_base.",
                model_name
            )

    def count_tokens(self, text: str) -> int:
        """Count tokens in a string."""
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def format_usage_summary(self, total_tokens: int) -> str:
        """Create a summary string for usage reporting.
        
        Matches the format required by development.md:
        token usage:
        search <tokens>
        """
        return f"\ntoken usage:\nsearch  {total_tokens}"

token_manager = TokenManager()
