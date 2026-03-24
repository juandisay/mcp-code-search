"""Entry point — FastAPI management + MCP server."""
import os
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

from config import config
from core.searcher import CodeSearcher
from core.token_manager import token_manager
from core.watcher import ProjectWatcher
from core.rule_manager import rule_manager

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s [%(levelname)s]"
        " %(name)s: %(message)s"
    ),
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------- #
#  Core Services                                            #
# --------------------------------------------------------- #
indexer = CodeIndexer()
searcher = CodeSearcher()
watcher = ProjectWatcher(indexer)

# --------------------------------------------------------- #
#  MCP Server                                               #
# --------------------------------------------------------- #
mcp = FastMCP("CodeMemoryMCP")


@mcp.tool()
def semantic_code_search(
    query: str,
    n_results: int = 3,
    project_name: str = None,
    max_distance: float = None,
) -> str:
    """Search for code snippets via NLP query.

    Args:
        query: What to find, e.g. 'S3 upload'.
        n_results: Number of results.
        project_name: Filter by project.
        max_distance: Relevance threshold.
    """
    results = searcher.search(
        query, n_results, project_name, max_distance
    )
    if not results:
        return "No relevant code snippets found."

    lines = []
    for i, res in enumerate(results):
        dist = res.get("distance")
        dist_info = (
            f" (distance: {dist:.4f})"
            if dist is not None
            else ""
        )
        proj = res.get("project_name", "Unknown")
        lines.append(
            f"--- Result {i + 1}{dist_info} ---\n"
            f"File: {res['file_path']}"
            f" (Line {res['start_line']})\n"
            f"Project: {proj}\n"
            f"Code:\n{res['snippet']}\n"
        )
    
    output = "\n".join(lines)
    total_tokens = token_manager.count_tokens(output)
    return output + token_manager.format_usage_summary(total_tokens)


@mcp.tool()
def index_folder(folder_path: str) -> str:
    """Index a local project folder.

    Args:
        folder_path: Absolute path to the folder.
    """
    if not os.path.isdir(folder_path):
        return (
            f"Error: '{folder_path}' does not exist"
            " or is not a directory."
        )

    try:
        summary = indexer.index_project_folder(
            folder_path
        )
        # Start watching after initial index
        watcher.start(folder_path)
        # For indexing, we can't easily count tokens of everything 
        # without reading it all again, but CodeIndexer already 
        # has the content during processing.
        # Let's just report success here.
        return (
            f"Successfully indexed: {folder_path}\n"
            f"Files processed: "
            f"{summary['files_processed']}, "
            f"Skipped: {summary['files_skipped']}, "
            f"Chunks: {summary['chunks_upserted']}\n"
            f"Total tokens indexed: {summary['total_tokens']}"
        )
    except Exception as e:
        return f"Error during indexing: {e}"


@mcp.tool()
def list_indexed_projects() -> str:
    """List all indexed project names."""
    projects = indexer.list_projects()
    if not projects:
        return "No projects have been indexed yet."
    return "Indexed projects:\n" + "\n".join(
        f"  - {p}" for p in projects
    )


@mcp.tool()
def get_index_stats() -> str:
    """Get code search index statistics."""
    collection = indexer.collection
    count = collection.count()
    projects = indexer.list_projects()
    proj_str = (
        ", ".join(projects) if projects else "none"
    )
    return (
        f"Total indexed chunks: {count}\n"
        f"Collection: {collection.name}\n"
        f"Storage: {config.CHROMA_DATA_PATH}\n"
        f"Projects ({len(projects)}): {proj_str}"
    )


@mcp.tool()
def sync_agent_rules(folder_path: str, context_notes: str = "") -> str:
    """Initialize or update Antigravity agent rules for a project based on its detected stack.
    
    Args:
        folder_path: Absolute path to the project.
        context_notes: Additional custom requirements or context to inject.
    """
    if not os.path.isdir(folder_path):
        return f"Error: '{folder_path}' does not exist or is not a directory."
        
    try:
        overview = rule_manager.sync_rules(folder_path, context_notes)
        init_str = ", ".join(overview["initialized"]) or "None"
        up_str = ", ".join(overview["updated"]) or "None"
        skip_str = ", ".join(overview["skipped"]) or "None"
        
        return (
            f"Rule Sync Complete for {folder_path}\n"
            f"Initialized: {init_str}\n"
            f"Updated: {up_str}\n"
            f"Skipped: {skip_str}"
        )
    except Exception as e:
        return f"Error syncing rules: {e}"


# --------------------------------------------------------- #
#  FastAPI Server (Management Layer)                        #
# --------------------------------------------------------- #


def _run_background_indexing(folder_path: str):
    """Run indexing in a background thread."""
    if os.path.isdir(folder_path):
        try:
            summary = indexer.index_project_folder(
                folder_path
            )
            logger.info(
                "Auto-indexing done for %s — Chunks: %s, Tokens: %s",
                folder_path, summary['chunks_upserted'], summary['total_tokens']
            )
            # Start watching after initial index
            watcher.start(folder_path)
        except Exception as e:
            logger.error(
                "Error during auto-indexing: %s", e
            )
    else:
        logger.warning(
            "Auto-index folder ignored: %s "
            "(does not exist)", folder_path,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-index on startup (PRD §6.2)."""
    if config.PROJECT_FOLDER_TO_INDEX:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            _run_background_indexing,
            config.PROJECT_FOLDER_TO_INDEX,
        )
    yield
    if 'watcher' in globals() and watcher:
        watcher.stop()


app = FastAPI(
    title="Code-Memory API",
    description="Local code index for semantic search",
    version="1.0.0",
    lifespan=lifespan,
)


class IndexRequest(BaseModel):
    """POST /index request body."""

    folder_path: str


class SyncRequest(BaseModel):
    """POST /sync-rules request body."""

    folder_path: str
    context_notes: str = ""


@app.post("/index")
async def api_index_folder(
    req: IndexRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger indexing of a folder (PRD §6.2)."""
    if not os.path.isdir(req.folder_path):
        raise HTTPException(
            status_code=400,
            detail="Invalid folder path",
        )

    background_tasks.add_task(
        _run_background_indexing, req.folder_path
    )
    return {
        "message": "Indexing started in background",
        "folder_path": req.folder_path,
    }


@app.get("/stats")
async def api_stats():
    """Return ChromaDB stats (PRD §6.2)."""
    collection = indexer.collection
    count = collection.count()
    projects = indexer.list_projects()
    return {
        "total_indexed_chunks": count,
        "collection_name": collection.name,
        "chroma_data_path": config.CHROMA_DATA_PATH,
        "indexed_projects": projects,
    }


@app.post("/sync-rules")
async def api_sync_rules(req: SyncRequest):
    """Trigger agent rules initialization/updating."""
    if not os.path.isdir(req.folder_path):
        raise HTTPException(
            status_code=400,
            detail="Invalid folder path",
        )
        
    try:
        overview = rule_manager.sync_rules(req.folder_path, req.context_notes)
        return {"message": "Rules synced", "overview": overview}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------- #
#  Entry Point                                              #
# --------------------------------------------------------- #
if __name__ == "__main__":
    import sys

    if "--mcp" in sys.argv:
        logger.info(
            "Starting MCP server (stdio)..."
        )
        mcp.run()
    else:
        import uvicorn

        logger.info(
            "Starting FastAPI on "
            "http://127.0.0.1:8000 ..."
        )
        uvicorn.run(
            app, host="127.0.0.1", port=8000
        )
