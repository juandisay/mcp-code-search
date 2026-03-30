import asyncio
import logging
import os

from mcp.server.fastmcp import FastMCP

from core.chat_context import chat_context_manager
from core.context_assembler import context_assembler
from core.dependencies import get_indexer, get_searcher
from core.job_manager import job_manager, planning_job_manager
from core.mahaguru_client import mahaguru_client
from core.rule_manager import rule_manager
from core.token_manager import token_manager
from core.utils import run_background_indexing

logger = logging.getLogger(__name__)

# --- Tool Implementations (Internal) ---

def semantic_code_search(
    query: str,
    n_results: int = 3,
    project_name: str = None,
    max_distance: float = None,
    language: list[str] = None,
    file_path_includes: str = None,
    excluded_dirs: list[str] = None,
    re_rank: bool = None,
) -> str:
    """Search for code snippets via NLP query."""
    results = get_searcher().search(
        query, n_results, project_name, max_distance,
        language=language, file_path_includes=file_path_includes,
        excluded_dirs=excluded_dirs, re_rank=re_rank
    )
    output = context_assembler.format_search_results(results)
    total_tokens = token_manager.count_tokens(output)
    return output + token_manager.format_usage_summary(total_tokens)

async def index_folder(folder_path: str) -> str:
    """Index a local project folder asynchronously."""
    if not os.path.isdir(folder_path):
        return f"Error: '{folder_path}' does not exist or is not a directory."

    # Prevent concurrent indexing of the same folder
    if not job_manager.start_job(folder_path):
        return f"Notice: Indexing is already in progress for '{folder_path}'."

    # Fire-and-forget background task using asyncio.to_thread to offload sync I/O
    asyncio.create_task(asyncio.to_thread(run_background_indexing, folder_path))

    return (
        f"Indexing for '{folder_path}' has been initiated in the background.\n"
        f"This may take a few minutes for larger repositories. "
        f"Use the 'get_index_stats' tool to monitor current status."
    )

def list_indexed_projects() -> str:
    """List all indexed project names."""
    projects = get_indexer().list_projects()
    if not projects:
        return "No projects have been indexed yet."
    return "Indexed projects:\n" + "\n".join(f"  - {p}" for p in projects)

def delete_project(project_name: str) -> str:
    """Delete an indexed project and all its data."""
    try:
        summary = get_indexer().delete_project(project_name)
        if summary["deleted_chunks"] == 0:
            return f"Project '{project_name}' not found or already empty."

        return (
            f"Successfully deleted project: {project_name}\n"
            f"Chunks removed: {summary['deleted_chunks']}\n"
            f"Files removed from index: {summary['deleted_files']}"
        )
    except Exception as e:
        return f"Error deleting project: {e}"

def maintenance_prune() -> str:
    """Scan and remove stale files/projects from the index that no longer exist on disk."""
    try:
        summary = get_indexer().prune_stale_files()
        return (
            f"Maintenance Complete:\n"
            f"  - Stale files removed: {summary['pruned_files']}\n"
            f"  - Non-existent project roots removed: {summary['pruned_roots']}"
        )
    except Exception as e:
        return f"Error during maintenance: {e}"

def get_index_stats() -> str:
    """Get code search index statistics and active background jobs."""
    indexer = get_indexer()
    collection = indexer.collection
    count = collection.count()
    projects = indexer.list_projects()
    proj_str = ", ".join(projects) if projects else "none"

    # Active Background Jobs status feedback
    active_idx_jobs = job_manager.get_active_jobs()
    idx_str = "None"
    if active_idx_jobs:
        idx_str = "\n".join([f"  - {path}: {status}" for path, status in active_idx_jobs.items()])

    # Active Background Planning Jobs
    active_plan_jobs = planning_job_manager.get_active_jobs()
    plan_str = "None"
    if active_plan_jobs:
        plan_str = "\n".join([f"  - {jid}: {brief}" for jid, brief in active_plan_jobs.items()])

    return (
        f"--- Index Statistics ---\n"
        f"Total indexed chunks: {count}\n"
        f"Projects ({len(projects)}): {proj_str}\n\n"
        f"--- Active Indexing Jobs ---\n"
        f"{idx_str}\n\n"
        f"--- Active Planning Jobs ---\n"
        f"{plan_str}"
    )

def sync_agent_rules(folder_path: str, context_notes: str = "") -> str:
    """Init or update Antigravity agent rules based on its detected stack."""
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

async def request_mahaguru_refinement(
    refinement_brief: str,
    relevant_files: list[str] = None
) -> str:
    """Escalate a task to the Mahaguru (Teacher/Planner) model for refinement."""
    logger.info("Mahaguru refinement requested...")

    full_context = context_assembler.assemble_refinement_context(
        refinement_brief,
        relevant_files
    )

    response_text, structured_plan = await mahaguru_client.get_refinement(
        refinement_brief,
        code_context=full_context
    )

    # PILLAR IV: If we have a structured plan, we can log it or process it.
    # For the MCP output, we return the text, but the structured plan is available.
    if structured_plan:
        logger.info("Mahaguru provided a structured plan with %d tasks.", len(structured_plan.get("tasks", [])))

    output = (
        "--- MAHAGURU REFINEMENT RESPONSE ---\n\n"
        f"{response_text}\n\n"
        "--- END OF REFINEMENT ---"
    )

    total_tokens = token_manager.count_tokens(output)
    return output + token_manager.format_usage_summary(total_tokens)

# --- Async Refinement Implementation ---

async def _run_background_refinement(job_id: str, refinement_brief: str, relevant_files: list[str] = None):
    """Background coroutine that awaits Mahaguru and updates the job manager."""
    try:
        full_context = context_assembler.assemble_refinement_context(
            refinement_brief,
            relevant_files
        )
        response_text, _ = await mahaguru_client.get_refinement(
            refinement_brief,
            code_context=full_context
        )

        output = (
            "--- MAHAGURU REFINEMENT RESPONSE ---\n\n"
            f"{response_text}\n\n"
            "--- END OF REFINEMENT ---"
        )
        planning_job_manager.complete_job(job_id, output)
    except Exception as e:
        logger.error(f"Background planning job {job_id} failed: {e}")
        planning_job_manager.fail_job(job_id, f"Error during refinement: {str(e)}")

async def request_async_mahaguru_refinement(
    refinement_brief: str,
    relevant_files: list[str] = None
) -> str:
    """
    Trigger a complex planning task in the background. 
    Returns a Job ID immediately so the agent can continue other work.
    """
    job_id = planning_job_manager.create_job(refinement_brief)

    # Fire-and-forget the background task
    asyncio.create_task(
        _run_background_refinement(job_id, refinement_brief, relevant_files)
    )

    return (
        f"Background planning job initiated successfully.\n"
        f"Job ID: {job_id}\n"
        f"You may now perform other tasks. Use 'get_planning_job_result' with this Job ID to check status or retrieve the result."
    )

def get_planning_job_result(job_id: str) -> str:
    """
    Check the status or retrieve the result of an asynchronous planning job.
    If completed, this will return the plan and clear the job from memory.
    """
    job = planning_job_manager.check_status(job_id)

    if not job:
        return f"Error: Job ID '{job_id}' not found. It may have already been retrieved or never existed."

    if job["status"] == "Running":
        return f"Job '{job_id}' is still Running. Mahaguru is currently thinking. Please check back later."

    # If Completed or Failed, pop it to clean up memory
    job_data = planning_job_manager.pop_job(job_id)

    if job_data["status"] == "Failed":
        return f"Job '{job_id}' Failed.\nDetails: {job_data['result']}"

    # Success
    return job_data["result"]

def get_project_chat_context(project_name: str) -> str:
    """Retrieve the last session's chat context/summary for a specific project."""
    context = chat_context_manager.get_context(project_name)
    if context:
        return f"Previous context found for '{project_name}':\n\n{context}"
    return f"No previous context found for '{project_name}'. This is a fresh start."

def save_project_chat_context(project_name: str, summary: str) -> str:
    """
    Save a summary of the current session for a project. 
    CRITICAL: The 'summary' string MUST be formatted exactly with these 4 bullet points:
    - Objective: [...]
    - Completed: [...]
    - Pending/Blockers: [...]
    - Next Steps: [...]
    """
    if not summary or len(summary.strip()) < 20:
        return "Error: Summary is too short. Please provide a detailed 4-bullet summary (min 20 chars)."

    chat_context_manager.save_context(project_name, summary)
    return f"Successfully saved chat context for '{project_name}'."

# --- Registration ---

def register_mcp_tools(mcp: FastMCP):
    """Bridge all logical tools to the MCP transport layer."""
    mcp.tool()(semantic_code_search)
    mcp.tool()(index_folder)
    mcp.tool()(list_indexed_projects)
    mcp.tool()(delete_project)
    mcp.tool()(maintenance_prune)
    mcp.tool()(get_index_stats)
    mcp.tool()(sync_agent_rules)
    mcp.tool()(request_mahaguru_refinement)
    mcp.tool()(request_async_mahaguru_refinement)
    mcp.tool()(get_planning_job_result)
    mcp.tool()(get_project_chat_context)
    mcp.tool()(save_project_chat_context)
