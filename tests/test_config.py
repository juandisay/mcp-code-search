"""Tests for config module."""
from config import Settings, config


class TestConfig:
    """Tests for project configuration."""

    def test_default_chroma_data_path(self):
        """Default CHROMA_DATA_PATH is 'data'."""
        s = Settings()
        assert s.CHROMA_DATA_PATH == "data"

    def test_default_chunk_size(self):
        """Default CHUNK_SIZE is 1000."""
        s = Settings()
        assert s.CHUNK_SIZE == 1000

    def test_default_chunk_overlap(self):
        """Default CHUNK_OVERLAP is 200."""
        s = Settings()
        assert s.CHUNK_OVERLAP == 200

    def test_default_batch_size(self):
        """Default BATCH_SIZE is 100."""
        s = Settings()
        assert s.BATCH_SIZE == 100

    def test_default_max_distance(self):
        """Default MAX_DISTANCE is 2.0."""
        s = Settings()
        assert s.MAX_DISTANCE == 2.0

    def test_config_singleton_loads(self):
        """Global config object loads without error."""
        assert config is not None
        assert isinstance(config, Settings)
