---
description: Development setup — venv, linting, and testing workflow
---

# Development Workflow

## 1. Activate Virtual Environment

// turbo-all

```bash
source venv/bin/activate
```

Always activate venv before running any Python
command.

## 2. Install Dependencies

```bash
pip install -r requirements.txt
pip install pytest flake8
```

## 3. Lint with Flake8 (PEP 8, max-length 80)

Run flake8 on all project source files:

```bash
flake8 --max-line-length=80 \
  main.py config.py core/ tests/
```

Fix all reported issues before committing.

## 4. Run Tests

All tests live in the `tests/` directory and use
`pytest`.

```bash
pytest tests/ -v
```

## 5. Writing New Tests

- Create test files in `tests/` with the naming
  convention `test_<module>.py`.
- Use `pytest` fixtures and assertions.
- Each test function should start with `test_`.
- Group related tests in classes prefixed with
  `Test` (e.g. `TestCodeIndexer`).
- Use `tmp_path` fixture for temporary directories.
- Follow PEP 8 and max line length of 80 chars in
  test files too.

Example test structure:

```python
import pytest
from core.indexer import CodeIndexer


class TestCodeIndexer:
    def test_index_project_folder(self, tmp_path):
        # Create sample files in tmp_path
        sample = tmp_path / "hello.py"
        sample.write_text("def hello(): pass")

        indexer = CodeIndexer()
        result = indexer.index_project_folder(
            str(tmp_path)
        )
        assert result["files_processed"] > 0
```

## 6. Full Pre-Commit Check

Run lint + tests together:

```bash
flake8 --max-line-length=80 \
  main.py config.py core/ tests/ \
  && pytest tests/ -v
```
