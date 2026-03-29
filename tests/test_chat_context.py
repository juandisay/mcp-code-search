import os
import shutil
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.chat_context import ChatContextManager


class TestChatContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a temporary test data dir
        cls.test_data_dir = Path("./test_data_chat")
        cls.test_data_dir.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        # Clean up test data
        if cls.test_data_dir.exists():
            shutil.rmtree(cls.test_data_dir)

    def setUp(self):
        # Initialize a fresh manager for each test, injecting the test dir
        self.manager = ChatContextManager(db_dir=str(self.test_data_dir))

    def test_save_and_get_context(self):
        project = "MyTestProject"
        summary = "Objective: Test chat context.\nCompleted: Implementation.\nPending: Verification.\nNext Steps: Deploy."

        self.manager.save_context(project, summary)
        retrieved = self.manager.get_context(project)

        self.assertIsNotNone(retrieved)
        self.assertIn("Objective: Test chat context.", retrieved)
        self.assertIn("[Last Updated:", retrieved)

    def test_normalization_collision_prevention(self):
        # Ensure two projects with the same basename do not collide
        project_1 = "/Users/test/clientA/backend"
        project_2 = "/Users/test/clientB/backend"

        self.manager.save_context(project_1, "Client A Summary")
        self.manager.save_context(project_2, "Client B Summary")

        retrieved_1 = self.manager.get_context(project_1)
        retrieved_2 = self.manager.get_context(project_2)

        self.assertIn("Client A Summary", retrieved_1)
        self.assertIn("Client B Summary", retrieved_2)
        self.assertNotEqual(retrieved_1, retrieved_2)

    def test_overwrite_context(self):
        project = "OverwriteTest"
        self.manager.save_context(project, "First Summary")
        self.manager.save_context(project, "Second Summary")

        retrieved = self.manager.get_context(project)
        self.assertIn("Second Summary", retrieved)
        self.assertNotIn("First Summary", retrieved)

    def test_nonexistent_context(self):
        retrieved = self.manager.get_context("NonExistent")
        self.assertIsNone(retrieved)

if __name__ == '__main__':
    unittest.main()
