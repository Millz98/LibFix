import pytest
import tempfile
import os
from src.core.dependency_parser import (
    parse_requirements_txt,
    parse_setup_py,
    parse_pyproject_toml,
)


class TestRequirementsParser:
    def test_parses_simple_requirements(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("requests>=2.28.0\nflask>=2.0\n")
            f.write("# This is a comment\n")
            f.write("django==4.0.0\n")
            temp_path = f.name

        try:
            deps = parse_requirements_txt(temp_path)
            assert len(deps) == 3
            assert "requests>=2.28.0" in deps
            assert "flask>=2.0" in deps
            assert "django==4.0.0" in deps
        finally:
            os.unlink(temp_path)

    def test_ignores_comments(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("# comment\npytest\n# another comment\n")
            temp_path = f.name

        try:
            deps = parse_requirements_txt(temp_path)
            assert len(deps) == 1
            assert deps[0] == "pytest"
        finally:
            os.unlink(temp_path)

    def test_handles_nonexistent_file(self):
        deps = parse_requirements_txt("/nonexistent/file.txt")
        assert deps == []


class TestSetupPyParser:
    def test_parses_simple_install_requires(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("setup(\n    install_requires=['requests>=2.28', 'flask']\n)\n")
            temp_path = f.name

        try:
            deps = parse_setup_py(temp_path)
            assert len(deps) == 2
            assert any("requests" in d for d in deps)
            assert any("flask" in d for d in deps)
        finally:
            os.unlink(temp_path)

    def test_handles_multiline_install_requires(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("setup(\n    install_requires=[\n        'requests>=2.28',\n        'flask',\n    ]\n)\n")
            temp_path = f.name

        try:
            deps = parse_setup_py(temp_path)
            assert len(deps) == 2
        finally:
            os.unlink(temp_path)


class TestPyprojectTomlParser:
    def test_parses_poetry_dependencies(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""
[tool.poetry]
name = "test-project"

[tool.poetry.dependencies]
python = "^3.8"
requests = "^2.28"
flask = "^2.0"
""")
            temp_path = f.name

        try:
            deps = parse_pyproject_toml(temp_path)
            assert len(deps) == 2
            assert any("requests" in d for d in deps)
            assert any("flask" in d for d in deps)
        finally:
            os.unlink(temp_path)

    def test_parses_pep621_dependencies(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""
[project]
name = "test-project"
dependencies = ["requests>=2.28", "flask>=2.0"]

[build-system]
requires = ["setuptools"]
""")
            temp_path = f.name

        try:
            deps = parse_pyproject_toml(temp_path)
            assert len(deps) == 2
        finally:
            os.unlink(temp_path)
