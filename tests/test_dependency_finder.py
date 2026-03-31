import pytest
from src.core.dependency_finder import find_dependency_files, DependencyFiles


class TestDependencyFinder:
    def test_returns_correct_structure(self):
        result = find_dependency_files(".")
        assert isinstance(result, dict)
        assert "requirements" in result
        assert "setup" in result
        assert "pyproject" in result

    def test_nonexistent_directory_returns_empty(self):
        result = find_dependency_files("/nonexistent/path/12345")
        assert result["requirements"] == []
        assert result["setup"] == []
        assert result["pyproject"] == []

    def test_current_directory_scan(self):
        result = find_dependency_files(".")
        assert isinstance(result["requirements"], list)
        assert isinstance(result["setup"], list)
        assert isinstance(result["pyproject"], list)
