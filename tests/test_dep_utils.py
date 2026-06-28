import pytest
from src.utils.dep_utils import extract_package_name


class TestExtractPackageName:
    def test_simple_name(self):
        assert extract_package_name("requests") == "requests"

    def test_with_version_greater_than(self):
        assert extract_package_name("requests>=2.28") == "requests"

    def test_with_version_equal(self):
        assert extract_package_name("flask==2.0.0") == "flask"

    def test_with_version_range(self):
        assert extract_package_name("Django>=4.0,<5.0") == "Django"

    def test_with_extras(self):
        assert extract_package_name("psycopg2[binary]") == "psycopg2"

    def test_with_environment_marker(self):
        assert extract_package_name("toml; python_version < '3.11'") == "toml"

    def test_with_release_notation(self):
        assert extract_package_name("numpy!=1.21.0") == "numpy"

    def test_name_with_hyphens(self):
        assert extract_package_name("python-dateutil>=2.8.2") == "python-dateutil"

    def test_empty_string(self):
        assert extract_package_name("") == ""

    def test_whitespace_only(self):
        assert extract_package_name("   ") == ""
