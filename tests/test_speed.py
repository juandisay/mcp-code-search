import logging
import time

from core.dependencies import get_searcher

logger = logging.getLogger(__name__)

def test_search_inference_speed():
    """Performance test to ensure CodeSearcher response times are within expected bounds."""
    query = "nps-feedback"
    logger.info("Initializing searcher (loading model)...")
    searcher = get_searcher()

    # Warm-up search (handles cold cache and model loading overhead)
    logger.info(f"Warm-up search for: '{query}'")
    searcher.search(query=query, n_results=5)

    # Timed search
    logger.info(f"Timed search (n_results=150) for: '{query}'")
    start_time = time.time()
    res = searcher.search(query=query, n_results=150)
    end_time = time.time()

    inference_time = end_time - start_time
    logger.info(f"Search result count: {len(res)}")
    logger.info(f"Inference took {inference_time:.4f} seconds")

    # Optional SLA assertion: inference should safely complete under 5 seconds
    # (adjust threshold as needed based on hardware/environment)
    assert inference_time < 5.0, f"Search inference took too long: {inference_time:.4f}s"
