import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

class ChatContextManager:
    """Manages project-specific chat context/summaries in a SQLite database."""

    def __init__(self, db_dir: Optional[str] = None):
        # Dependency Injection for easier testing
        base_dir = db_dir if db_dir else config.CHROMA_DATA_PATH
        self.db_path = Path(base_dir) / "chat_context.sqlite"
        self._init_db()

    def _get_connection(self):
        """Returns a configured SQLite connection with WAL enabled for concurrency."""
        # timeout=10 prevents immediate locking errors in threaded environments
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        """Initializes the SQLite database with the required schema."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS project_context (
                        project_name TEXT PRIMARY KEY,
                        summary TEXT NOT NULL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
        except Exception as e:
            logger.error(f"Failed to initialize ChatContext database at {self.db_path}: {e}")

    def _normalize_name(self, project_name: str) -> str:
        """
        Ensure consistent, collision-free project naming.
        Converts absolute paths to a flat, safe string (e.g., /a/b/c -> a_b_c).
        """
        name = project_name.strip().lower()
        if not name:
            return "default"

        # If it looks like a path, make it absolute to ensure uniqueness
        if '/' in name or '\\' in name:
            name = os.path.abspath(name)

        # Replace non-alphanumeric characters with underscores
        safe_name = re.sub(r'[^a-z0-9]+', '_', name).strip('_')
        return safe_name if safe_name else "default"

    def get_context(self, project_name: str) -> Optional[str]:
        """Retrieves the last session's chat context/summary for a specific project."""
        name = self._normalize_name(project_name)
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT summary, last_updated FROM project_context WHERE project_name = ?",
                    (name,)
                )
                row = cursor.fetchone()
                if row:
                    # Return both summary and the timestamp for user reference
                    return f"[Last Updated: {row[1]}]\n{row[0]}"
                return None
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving context for '{name}': {e}")
            return None

    def save_context(self, project_name: str, summary: str):
        """Saves or updates the chat context summary for a specific project."""
        name = self._normalize_name(project_name)
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO project_context (project_name, summary, last_updated) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (name, summary)
                )
                conn.commit()
            logger.info(f"Successfully saved chat context for '{name}'.")
        except sqlite3.Error as e:
            logger.error(f"Database error saving context for '{name}': {e}")

# Global instance for easy access
chat_context_manager = ChatContextManager()
