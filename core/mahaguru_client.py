import logging
import re
import httpx
from config import config

logger = logging.getLogger(__name__)

class MahaguruClient:
    """Asynchronous client for interacting with the Mahaguru (Teacher/Planner) model."""

    def __init__(self):
        self._client = httpx.AsyncClient()
        # DEEP REASONING: Mahaguru (Planning) needs more time to analyze and 'think' (Pillar III).
        self.timeout = config.MAHAGURU_API_TIMEOUT

    async def close(self):
        """Close the internal HTTP client."""
        await self._client.aclose()

    async def get_refinement(self, refinement_brief: str, code_context: str = None, system_prompt: str = None) -> str:
        """Sends a refinement brief to Mahaguru and returns the response.
        
        Tries multiple models from config.MODELS in sequence if failures occur.
        """
        
        if not system_prompt:
            system_prompt = (
                "You are Mahaguru, a Senior Technical Architect and Teacher. "
                "Your role is to refine the implementation strategy for a Worker model (Gemini Flash). "
                "Provide clear, high-level structural guidance, best practices, and a refined plan. "
                "Focus on robustness, scalability, and project-specific consistency.\n\n"
                "CRITICAL INSTRUCTION: You must begin your response with a <thinking> block. "
                "Inside this block, analyze the provided context, the user brief, and perform a "
                "step-by-step reasoning phase before proposing the architecture. "
                "After closing the </thinking> block, provide the final action-oriented implementation plan."
            )

        if not config.MAHAGURU_API_KEY:
            logger.error("MAHAGURU_API_KEY is not set in configuration.")
            return "Error: MAHAGURU_API_KEY is missing. Please set it in your .env file to enable AI Cascading."

        # Pre-flight context management (Pillar III)
        from core.token_manager import token_manager
        
        full_prompt = f"{system_prompt or ''}\n{refinement_brief}\n{code_context or ''}"
        estimated_tokens = token_manager.count_tokens(full_prompt)
        
        # If context is too large, truncate it
        if estimated_tokens > config.MAX_TOTAL_CONTEXT_TOKENS:
            logger.warning("Context too large (%d tokens). Truncating...", estimated_tokens)
            overage_ratio = config.MAX_TOTAL_CONTEXT_TOKENS / estimated_tokens
            if code_context:
                keep_chars = int(len(code_context) * overage_ratio * 0.9)
                code_context = code_context[:keep_chars] + "\n... (context truncated due to token limit) ...\n"

        api_url = f"{config.MAHAGURU_API_URL.rstrip('/')}/chat/completions"
        api_key = config.MAHAGURU_API_KEY.get_secret_value()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        errors = []
        for model_name in config.MODELS:
            logger.info("Attempting Mahaguru refinement with model: %s", model_name)
            
            user_content = f"Worker Refinement Brief:\n\n{refinement_brief}"
            if code_context:
                user_content += f"\n\n--- Code Context ---\n{code_context}\n--- End of Code Context ---"

            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.2,
                "max_tokens": 8192,  # Ensure enough space for the reasoning phase
            }

            try:
                response = await self._client.post(
                    api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                
                # Handle rate limits and server errors by switching models
                if response.status_code == 429:
                    logger.warning("Rate limit hit for model %s. Switching...", model_name)
                    errors.append(f"{model_name}: Rate limited (429)")
                    continue
                
                if response.status_code >= 500:
                    logger.warning("Server error (%d) for model %s. Switching...", response.status_code, model_name)
                    errors.append(f"{model_name}: Server error ({response.status_code})")
                    continue

                response.raise_for_status()
                data = response.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    raw_content = data["choices"][0]["message"]["content"]
                    logger.info("Successfully received refinement from model: %s", model_name)
                    
                    # Distillation Phase (Pillar III: Efficient context management)
                    # Support both <thinking> and <think> (DeepSeek-R1)
                    think_match = re.search(r'<(?:think|thinking)>(.*?)</(?:think|thinking)>', raw_content, flags=re.DOTALL | re.IGNORECASE)
                    if think_match:
                        thinking_process = think_match.group(1).strip()
                        logger.info("--- Mahaguru Thinking Process ---\n%s", thinking_process)
                        
                        # Strip thinking from the plan to keep the Worker focused
                        final_plan = re.sub(r'<(?:think|thinking)>.*?</(?:think|thinking)>', '', raw_content, flags=re.DOTALL | re.IGNORECASE).strip()
                    else:
                        final_plan = raw_content.strip()
                    
                    return final_plan
                else:
                    logger.error("Unexpected response format from model %s: %s", model_name, data)
                    errors.append(f"{model_name}: Unexpected format")
                    continue

            except httpx.HTTPStatusError as e:
                logger.error("HTTP status error for model %s: %s", model_name, e)
                errors.append(f"{model_name}: HTTP {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error("Request error for model %s: %s", model_name, e)
                errors.append(f"{model_name}: Connection error")
            except Exception as e:
                logger.error("Unexpected error for model %s: %s", model_name, e)
                errors.append(f"{model_name}: {str(e)}")

        # If we reach here, all models failed
        error_summary = "; ".join(errors)
        logger.error("All Mahaguru models failed: %s", error_summary)
        return f"Error: All Mahaguru models failed. Details: {error_summary}"

# Singleton instance
mahaguru_client = MahaguruClient()
