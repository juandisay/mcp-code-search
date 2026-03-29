import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Constants pointing to the base templates
BASE_RULES_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent / "IDE" / "antigravity" / ".agents" / "rules"

class RuleManager:
    """Manages the creation and updates of Antigravity agent rules for dynamic projects."""

    @staticmethod
    def detect_stack(project_path: str) -> str:
        """Detect the technology stack based on root files."""
        path = Path(project_path)
        stack_parts = []

        if (path / "package.json").exists():
            if (path / "tsconfig.json").exists():
                stack_parts.append("Node.js (TypeScript)")
            else:
                stack_parts.append("Node.js (JavaScript)")

        if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists() or (path / "Pipfile").exists():
            stack_parts.append("Python")

        if (path / "go.mod").exists():
            stack_parts.append("Go")

        if (path / "pom.xml").exists() or (path / "build.gradle").exists():
            stack_parts.append("Java")

        if (path / "Cargo.toml").exists():
            stack_parts.append("Rust")

        if (path / "composer.json").exists():
            stack_parts.append("PHP")

        if (path / "Gemfile").exists():
            stack_parts.append("Ruby")

        if not stack_parts:
            return "Generic / Undetected Stack"

        return " + ".join(stack_parts)

    @staticmethod
    def sync_rules(target_project_path: str, context_notes: str = "") -> dict:
        """Initialize or update the agent rules in the target project."""
        target_path = Path(target_project_path)
        if not target_path.exists() or not target_path.is_dir():
            raise ValueError(f"Target path does not exist or is not a directory: {target_project_path}")

        target_rules_dir = target_path / ".agents" / "rules"
        target_rules_dir.mkdir(parents=True, exist_ok=True)

        detected_stack = RuleManager.detect_stack(target_project_path)

        if context_notes:
            detected_stack += f"\n\n**Additional Context requirements:**\n{context_notes}"

        overview = {"initialized": [], "updated": [], "skipped": []}

        # Ensure we have the base templates
        if not BASE_RULES_DIR.exists():
            logger.error("Base rules directory not found at %s", BASE_RULES_DIR)
            return overview

        for template_file in BASE_RULES_DIR.glob("*.template"):
            base_name = template_file.name.replace(".template", "")
            target_file = target_rules_dir / base_name

            with open(template_file, "r", encoding="utf-8") as f:
                template_content = f.read()

            # If target DOES NOT exist -> Initialize
            if not target_file.exists():
                # Customize stack.md
                if base_name == "stack.md":
                    # Replace the Important block
                    placeholder = "> [!IMPORTANT]\n> This is a template. In a real project, replace this content with the actual technology stack detected in the repository (e.g., Python/FastAPI, Node/Next.js, etc.)."
                    replacement = f"> [!IMPORTANT]\n> Detected Stack: **{detected_stack}**\n>\n> This file was automatically generated and customized for this workspace."
                    template_content = template_content.replace(placeholder, replacement)

                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(template_content)
                overview["initialized"].append(base_name)

            # If target DOES exist -> Smart Update / Merge
            else:
                with open(target_file, "r", encoding="utf-8") as f:
                    existing_content = f.read()

                updated = False

                # Rule 1: check if initial-workflow lacks the REAL-TIME WATCHER update
                if base_name == "initial-workflow.md":
                    if "REAL-TIME WATCHER" not in existing_content:
                        # Find the performance boundary to append
                        if "## 🛠️ Performance & Memory" in existing_content:
                            new_rule = "\n- **REAL-TIME WATCHER**: There is an automatic filesystem watcher running in the background. You **DO NOT** need to re-trigger `index_folder` manually after creating or modifying code; the server incrementally indexes changes automatically."
                            # Replace old automatic re-indexing if it exists
                            if "AUTOMATIC RE-INDEXING" in existing_content:
                                lines = existing_content.split('\n')
                                new_lines = []
                                for line in lines:
                                    if "- **AUTOMATIC RE-INDEXING**" in line:
                                        new_lines.append(new_rule.strip())
                                    else:
                                        new_lines.append(line)
                                existing_content = "\n".join(new_lines)
                            else:
                                existing_content = existing_content.replace("## 🛠️ Performance & Memory", f"## 🛠️ Performance & Memory{new_rule}")

                            updated = True

                    # Marker-based sync for AI Cascading
                    MARKER_START = "<!-- MAHAGURU_AI_CASCADING_START -->"
                    MARKER_END = "<!-- MAHAGURU_AI_CASCADING_END -->"

                    if MARKER_START in template_content and MARKER_END in template_content:
                        import re
                        pattern = f"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}"
                        template_match = re.search(pattern, template_content, re.DOTALL)

                        if template_match:
                            new_section = template_match.group(0)

                            if MARKER_START in existing_content and MARKER_END in existing_content:
                                # Replace existing section
                                existing_content = re.sub(pattern, new_section, existing_content, flags=re.DOTALL)
                                updated = True
                            else:
                                # Append new section
                                existing_content = existing_content.strip() + f"\n\n{new_section}\n"
                                updated = True

                # Rule 2: Re-inject stack if it was completely lost or if requested
                if base_name == "stack.md":
                    placeholder = "> [!IMPORTANT]\n> This is a template"
                    if placeholder in existing_content:
                        replacement = f"> [!IMPORTANT]\n> Detected Stack: **{detected_stack}**\n>\n> This file was automatically customized for this workspace during sync."
                        existing_content = existing_content.replace(placeholder, replacement)
                        updated = True

                # Rule 3: Ensure AI Cascading protocol is updated with latest roles
                if base_name == "ai-cascading.md":
                    if "Worker Model" in existing_content and "Mahaguru Model" in existing_content:
                        # We could add more specific merge logic here if needed
                        pass

                if updated:
                    with open(target_file, "w", encoding="utf-8") as f:
                        f.write(existing_content)
                    overview["updated"].append(base_name)
                else:
                    overview["skipped"].append(base_name)

        return overview

rule_manager = RuleManager()
