import logging
from core.dependencies import get_indexer, get_watcher
from core.job_manager import job_manager

logger = logging.getLogger(__name__)

def run_background_indexing(folder_path: str):
    """Run indexing in a background thread, manage state, and start watcher."""
    try:
        # 1. Update status
        job_manager.update_job(folder_path, "Analyzing project & indexing files...")
        
        # 2. Perform indexing (blocking call within this background thread)
        indexer = get_indexer()
        summary = indexer.index_project_folder(folder_path)
        
        logger.info(
            "Background indexing complete for %s. Chunks: %s, Tokens: %s",
            folder_path, summary['chunks_upserted'], summary['total_tokens']
        )
        
        # 3. Start real-time folder watcher
        job_manager.update_job(folder_path, "Starting live watcher...")
        get_watcher().start(folder_path)
        
    except Exception as e:
        logger.error("Error during background indexing for %s: %s", folder_path, e)
    finally:
        # 4. CRITICAL: Always release the job lock to allow future indexing
        job_manager.finish_job(folder_path)
