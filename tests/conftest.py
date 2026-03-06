"""Pytest configuration for tests/ directory."""

# Ignore the dummy_project directory — it contains
# sample files for indexing tests, not actual tests.
collect_ignore_glob = ["dummy_project/*"]
