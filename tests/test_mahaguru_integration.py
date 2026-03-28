import asyncio
import logging
import sys
import os

# Ensure the project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mahaguru_client import mahaguru_client
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Manual integration test against the real local LLM endpoint."""
    print("--- REAL MAHAGURU INTEGRATION TEST ---")
    print(f"Target URL: {config.MAHAGURU_API_URL}")
    print(f"Target Model: {config.MODELS}")
    
    brief = "Test connection to Mahaguru. If you receive this, please reply: 'Connection Successful. I am ready to plan.'"
    
    print("\nSending brief...")
    try:
        response = await mahaguru_client.get_refinement(brief)
        print("\n--- RESPONSE FROM MAHAGURU ---")
        print(response)
        print("--- END OF RESPONSE ---\n")
        
        if "Successful" in response or "ready" in response:
            print("✅ TEST PASSED: Communication successful.")
        else:
            print("⚠️ TEST WARNING: Communication successful but response content unusual.")
            
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
