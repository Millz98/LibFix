import pytest
import os
import tempfile
from src.core.migration_guide import (
    get_migration_guide,
    scan_for_usages,
    generate_migration_summary,
    auto_replace_usages,
    MIGRATION_GUIDES,
)


class TestMigrationGuide:
    def test_toml_migration_guide(self):
        guide = get_migration_guide("toml", "tomllib")
        assert guide.old_package == "toml"
        assert guide.new_package == "tomllib"
        assert len(guide.general_notes) > 0

    def test_dateutil_migration_guide(self):
        guide = get_migration_guide("python-dateutil", "pendulum")
        assert guide.new_package == "pendulum"

    def test_pytz_migration_guide(self):
        guide = get_migration_guide("pytz", "zoneinfo")
        assert len(guide.general_notes) > 0

    def test_unknown_package_returns_empty_guide(self):
        guide = get_migration_guide("unknown-package", "new-package")
        assert guide.old_package == "unknown-package"
        assert len(guide.general_notes) == 0

    def test_scan_for_usages_nonexistent_dir(self):
        hints = scan_for_usages("/nonexistent/path", "requests")
        assert hints == []

    def test_generate_migration_summary(self):
        summary = generate_migration_summary("toml", "tomllib", "/tmp")
        assert "toml" in summary
        assert "tomllib" in summary
        assert "Migration Guide" in summary

    def test_migration_guides_defined(self):
        assert "toml" in MIGRATION_GUIDES
        assert "pytz" in MIGRATION_GUIDES
        assert "python-dateutil" in MIGRATION_GUIDES


class TestAutoReplaceUsages:
    def test_auto_replace_seaborn_import(self):
        temp_dir = tempfile.mkdtemp()
        py_file = os.path.join(temp_dir, "test_file.py")

        with open(py_file, "w") as f:
            f.write("import seaborn as sns\nimport pandas as pd\n")

        count, files = auto_replace_usages(temp_dir, "seaborn", "plotly")

        assert count == 1
        assert py_file in files

        with open(py_file, "r") as f:
            content = f.read()
        assert "import seaborn" not in content
        assert "import plotly.express as px" in content

        os.unlink(py_file)
        os.unlink(f"{py_file}.bak")
        os.rmdir(temp_dir)

    def test_auto_replace_pytz_timezone(self):
        temp_dir = tempfile.mkdtemp()
        py_file = os.path.join(temp_dir, "test_file.py")

        with open(py_file, "w") as f:
            f.write("import pytz\ntz = pytz.timezone('US/Eastern')\n")

        count, files = auto_replace_usages(temp_dir, "pytz", "zoneinfo")

        assert count == 1

        with open(py_file, "r") as f:
            content = f.read()
        assert "pytz.timezone" not in content
        assert "ZoneInfo(" in content

        os.unlink(py_file)
        os.unlink(f"{py_file}.bak")
        os.rmdir(temp_dir)

    def test_auto_replace_no_matches(self):
        temp_dir = tempfile.mkdtemp()
        py_file = os.path.join(temp_dir, "test_file.py")

        with open(py_file, "w") as f:
            f.write("import requests\n")

        count, files = auto_replace_usages(temp_dir, "seaborn", "plotly")

        assert count == 0
        assert files == []

        os.unlink(py_file)
        os.rmdir(temp_dir)
