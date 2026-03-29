"""Entry point — FastAPI management + MCP server orchestrator."""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from api.fastapi_routes import router as api_router
from api.mcp_tools import register_mcp_tools
from config import config
from core.dependencies import get_indexer, shutdown_dependencies
from core.logger import setup_logging
from core.utils import run_background_indexing

# 1. Transport-agnostic diagnostic setup
_MCP_MODE = "--mcp" in sys.argv
setup_logging(level=logging.INFO, mcp_mode=_MCP_MODE)
logger = logging.getLogger(__name__)

# 2. Define MCP Server and Register Tools
mcp = FastMCP("CodeMemoryMCP")
register_mcp_tools(mcp)

# 3. Define FastAPI Server with Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service lifecycles (Pillar III)."""
    # Initialize Core Service
    indexer = get_indexer()

    # Auto-index on startup if configured (PRD §6.2)
    if config.PROJECT_FOLDER_TO_INDEX:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            run_background_indexing,
            config.PROJECT_FOLDER_TO_INDEX,
        )

    yield

    # Graceful Shutdown
    logger.info("Lifespan: Shutting down services...")
    shutdown_dependencies()

app = FastAPI(
    title="Code-Memory API",
    description="Local code index for semantic search",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount FastAPI routes
app.include_router(api_router)

# 4. Process Entry Points
if __name__ == "__main__":
    if _MCP_MODE:
        logger.info("Starting MCP server (stdio transport)...")
        mcp.run()
    elif "--index" in sys.argv:
        try:
            idx = sys.argv.index("--index")
            if idx + 1 < len(sys.argv):
                folder = sys.argv[idx + 1]
                logger.info("Manual index triggered for: %s", folder)
                summary = get_indexer().index_project_folder(folder)
                print(f"\nIndexing Complete for {folder}")
                print(f"Files Processed: {summary['files_processed']}")
                print(f"Files Skipped: {summary['files_skipped']}")
                print(f"Total Chunks: {summary['chunks_upserted']}")
                print(f"Total Tokens: {summary['total_tokens']}\n")
            else:
                print("Error: Missing folder path after --index")
        except Exception as e:
            print(f"Error during manual indexing: {e}")
    else:
        import uvicorn
        logger.info("Starting FastAPI on http://127.0.0.1:8000 ...")
        uvicorn.run(app, host="127.0.0.1", port=8000)
