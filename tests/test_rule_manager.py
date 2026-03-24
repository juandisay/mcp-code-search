import os
from pathlib import Path
from core.rule_manager import RuleManager

def test_rule_manager_sync(tmp_path: Path):
    """Test that rule syncing initializes and updates templates correctly."""
    test_project = tmp_path / "test_project"
    test_project.mkdir()
    
    # Simulate a Node.js project
    (test_project / "package.json").write_text('{"name": "demo"}')
    
    # 1. Test Initialization
    overview = RuleManager.sync_rules(str(test_project), "Must strictly use Vite")
    
    assert "stack.md" in overview["initialized"]
    assert "initial-workflow.md" in overview["initialized"]
    
    rules_dir = test_project / ".agents" / "rules"
    stack_content = (rules_dir / "stack.md").read_text(encoding="utf-8")
    
    # Verify Stack Detection and Custom context insertion
    assert "Node.js (JavaScript)" in stack_content
    assert "Must strictly use Vite" in stack_content
    assert "This is a template" not in stack_content
    
    # 2. Test Update Merge Logic
    workflow_path = rules_dir / "initial-workflow.md"
    workflow_content = workflow_path.read_text(encoding="utf-8")
    
    # Simulate an old workflow missing the REAL-TIME WATCHER rule 
    # but containing the old AUTOMATIC RE-INDEXING rule
    old_workflow = workflow_content.replace(
        "- **REAL-TIME WATCHER**: There is an automatic filesystem watcher running in the background. You **DO NOT** need to re-trigger `index_folder` manually after creating or modifying code; the server incrementally indexes changes automatically.",
        "- **AUTOMATIC RE-INDEXING**: After every code implementation, modification, or creation, you **MUST** immediately re-trigger `index_folder` to ensure the vector database is always up-to-date."
    )
    workflow_path.write_text(old_workflow, encoding="utf-8")
    
    # Run sync again
    overview2 = RuleManager.sync_rules(str(test_project))
    
    # Stack shouldn't aggressively update unless missing completely
    assert "stack.md" in overview2["skipped"]
    
    # Workflow should recognize the missing REAL-TIME WATCHER and patch it in
    assert "initial-workflow.md" in overview2["updated"]
    
    updated_workflow = workflow_path.read_text(encoding="utf-8")
    assert "REAL-TIME WATCHER" in updated_workflow
    assert "AUTOMATIC RE-INDEXING" not in updated_workflow
