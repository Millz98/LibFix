import pytest
import tempfile
import os
from src.core.dependency_replacer import (
    replace_dependency,
    _extract_package_name,
    _replace_in_text,
    _replace_in_toml,
)


class TestDependencyReplacer:
    def test_extract_package_name_simple(self):
        assert _extract_package_name("requests>=2.28") == "requests"
        assert _extract_package_name("flask==2.0.0") == "flask"
        assert _extract_package_name("django<4.0") == "django"

    def test_replace_in_requirements_txt(self):
        import tempfile
        temp_dir = tempfile.mkdtemp()
        req_file = os.path.join(temp_dir, "requirements.txt")
        with open(req_file, 'w') as f:
            f.write("requests>=2.28\nflask>=2.0\n")

        result = replace_dependency(temp_dir, "flask>=2.0", "fastapi>=0.100")
        assert result.success is True

        with open(req_file, 'r') as f:
            content = f.read()
        assert "fastapi>=0.100" in content
        assert "flask>=2.0" not in content

        os.unlink(req_file)
        backup_path = f"{req_file}.bak"
        if os.path.exists(backup_path):
            os.unlink(backup_path)
        os.rmdir(temp_dir)

    def test_replace_in_pyproject_toml(self):
        temp_dir = tempfile.mkdtemp()
        toml_file = os.path.join(temp_dir, "pyproject.toml")
        with open(toml_file, 'w') as f:
            f.write('[project]\ndependencies = ["toml>=0.10", "requests"]\n')

        result = replace_dependency(temp_dir, "toml>=0.10", "tomllib>=1.0")
        assert result.success is True

        with open(toml_file, 'r') as f:
            content = f.read()
        assert "tomllib>=1.0" in content

        os.unlink(toml_file)
        backup_path = f"{toml_file}.bak"
        if os.path.exists(backup_path):
            os.unlink(backup_path)
        os.rmdir(temp_dir)

    def test_replace_nonexistent_dependency(self):
        result = replace_dependency(
            tempfile.gettempdir(),
            "nonexistent-package==1.0",
            "replacement==2.0"
        )
        assert result.success is False
        assert "Could not find" in result.message

    def test_replace_in_text_function(self):
        content = "toml>=0.10\nrequests>=2.28\n"
        new_content = _replace_in_text(content, "toml>=0.10", "tomllib>=1.0")
        assert "tomllib>=1.0" in new_content
        assert "toml>=0.10" not in new_content

    def test_replace_in_toml_function(self):
        content = 'dependencies = ["toml>=0.10", "requests"]'
        new_content = _replace_in_toml(content, "toml>=0.10", 'tomllib>=1.0')
        assert "tomllib>=1.0" in new_content
        assert 'toml>=0.10"' not in new_content
