import pytest
from src.utils.path_utils import get_python_interpreter_path


class TestPathUtils:
    def test_returns_executable_path(self):
        path = get_python_interpreter_path()
        assert path is not None
        assert isinstance(path, str)
        assert len(path) > 0

    def test_python_in_path(self):
        path = get_python_interpreter_path()
        assert "python" in path.lower()
