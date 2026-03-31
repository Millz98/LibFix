import pytest
import os
import tempfile
from src.core.dependency_auditor import (
    scan_imports,
    audit_dependencies,
    _extract_package_name,
    _normalize_package_name,
    KNOWN_STANDARD_LIB,
    PACKAGE_ALIASES,
    remove_unused_dependencies,
    add_missing_dependencies,
)


class TestDependencyAuditor:
    def test_extract_package_name(self):
        assert _extract_package_name("requests>=2.28") == "requests"
        assert _extract_package_name("flask==2.0.0") == "flask"
        assert _extract_package_name("django<4.0") == "django"
        assert _extract_package_name("numpy[test]") == "numpy"

    def test_normalize_package_name(self):
        assert _normalize_package_name("My-Package") == "my_package"
        assert _normalize_package_name("my_package") == "my_package"
        assert _normalize_package_name("requests") == "requests"

    def test_scan_imports(self):
        temp_dir = tempfile.mkdtemp()
        py_file = os.path.join(temp_dir, "test.py")

        with open(py_file, "w") as f:
            f.write("import requests\nfrom pandas import DataFrame\n")

        imports = scan_imports(temp_dir)

        assert "requests" in imports
        assert "pandas" in imports

        os.unlink(py_file)
        os.rmdir(temp_dir)

    def test_scan_imports_ignores_venv(self):
        temp_dir = tempfile.mkdtemp()
        venv_dir = os.path.join(temp_dir, "venv")
        os.makedirs(venv_dir)
        py_file = os.path.join(venv_dir, "test.py")

        with open(py_file, "w") as f:
            f.write("import requests\n")

        imports = scan_imports(temp_dir)

        assert "requests" not in imports

        os.unlink(py_file)
        os.rmdir(venv_dir)
        os.rmdir(temp_dir)

    def test_audit_used_dependency(self):
        temp_dir = tempfile.mkdtemp()
        py_file = os.path.join(temp_dir, "test.py")

        with open(py_file, "w") as f:
            f.write("import requests\n")

        result = audit_dependencies(temp_dir, ["requests", "flask"])

        assert len(result.unused_dependencies) == 1
        assert result.unused_dependencies[0].package_name == "flask"
        assert len(result.missing_dependencies) == 0

        os.unlink(py_file)
        os.rmdir(temp_dir)

    def test_audit_missing_dependency(self):
        temp_dir = tempfile.mkdtemp()
        py_file = os.path.join(temp_dir, "test.py")

        with open(py_file, "w") as f:
            f.write("import requests\nimport missing_pkg\n")

        result = audit_dependencies(temp_dir, ["requests"])

        assert len(result.missing_dependencies) == 1
        assert result.missing_dependencies[0][0] == "missing_pkg"

        os.unlink(py_file)
        os.rmdir(temp_dir)

    def test_audit_all_used(self):
        temp_dir = tempfile.mkdtemp()
        py_file = os.path.join(temp_dir, "test.py")

        with open(py_file, "w") as f:
            f.write("import requests\nimport pandas\n")

        result = audit_dependencies(temp_dir, ["requests", "pandas"])

        assert len(result.unused_dependencies) == 0
        assert len(result.missing_dependencies) == 0

        os.unlink(py_file)
        os.rmdir(temp_dir)

    def test_known_standard_lib_ignored(self):
        assert "os" in KNOWN_STANDARD_LIB
        assert "sys" in KNOWN_STANDARD_LIB
        assert "json" in KNOWN_STANDARD_LIB
        assert "unittest" in KNOWN_STANDARD_LIB
        assert "heapq" in KNOWN_STANDARD_LIB
        assert "traceback" in KNOWN_STANDARD_LIB

    def test_sklearn_alias_recognized(self):
        temp_dir = tempfile.mkdtemp()
        py_file = os.path.join(temp_dir, "test.py")

        with open(py_file, "w") as f:
            f.write("from sklearn import datasets\n")

        result = audit_dependencies(temp_dir, ["scikit-learn"])

        assert len(result.missing_dependencies) == 0

        os.unlink(py_file)
        os.rmdir(temp_dir)


class TestFixDependencies:
    def test_remove_unused_from_requirements(self):
        temp_dir = tempfile.mkdtemp()
        req_file = os.path.join(temp_dir, "requirements.txt")

        with open(req_file, "w") as f:
            f.write("requests\nflask\nunused-pkg\n")

        count, files = remove_unused_dependencies(temp_dir, ["unused-pkg"])

        assert count == 1
        with open(req_file, "r") as f:
            content = f.read()
        assert "unused-pkg" not in content
        assert "requests" in content

        os.unlink(req_file)
        os.unlink(f"{req_file}.bak")
        os.rmdir(temp_dir)

    def test_add_missing_to_requirements(self):
        temp_dir = tempfile.mkdtemp()
        req_file = os.path.join(temp_dir, "requirements.txt")

        with open(req_file, "w") as f:
            f.write("requests\n")

        count, files = add_missing_dependencies(temp_dir, ["flask", "numpy"])

        assert count == 1
        with open(req_file, "r") as f:
            content = f.read()
        assert "flask" in content
        assert "numpy" in content

        os.unlink(req_file)
        os.rmdir(temp_dir)
