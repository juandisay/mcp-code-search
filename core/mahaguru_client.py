import logging
import httpx
from config import config

logger = logging.getLogger(__name__)

class MahaguruClient:
    """Asynchronous client for interacting with the Mahaguru (Teacher/Planner) model."""

    def __init__(self):
        self._client = httpx.AsyncClient()
        self.timeout = 60.0  # Planning might take longer

    async def close(self):
        """Close the internal HTTP client."""
        await self._client.aclose()

    async def get_refinement(self, refinement_brief: str, system_prompt: str = None) -> str:
        """Sends a refinement brief to Mahaguru and returns the response.
        
        Tries multiple models from config.MODELS in sequence if failures occur.
        """
        
        if not system_prompt:
            system_prompt = (
                "You are Mahaguru, a Senior Technical Architect and Teacher. "
                "Your role is to refine the implementation strategy for a Worker model (Gemini Flash). "
                "Provide clear, high-level structural guidance, best practices, and a refined plan. "
                "Focus on robustness, scalability, and project-specific consistency."
            )

        if not config.MAHAGURU_API_KEY:
            logger.error("MAHAGURU_API_KEY is not set in configuration.")
            return "Error: MAHAGURU_API_KEY is missing. Please set it in your .env file to enable AI Cascading."

        api_url = f"{config.MAHAGURU_API_URL.rstrip('/')}/chat/completions"
        api_key = config.MAHAGURU_API_KEY.get_secret_value()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        errors = []
        for model_name in config.MODELS:
            logger.info("Attempting Mahaguru refinement with model: %s", model_name)
            
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Worker Refinement Brief:\n\n{refinement_brief}"}
                ],
                "temperature": 0.2,
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
                    logger.info("Successfully received refinement from model: %s", model_name)
                    return data["choices"][0]["message"]["content"]
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
