import pytest
from src.core.alternatives import (
    find_alternatives,
    add_replacement,
    get_all_replacements,
    COMMON_REPLACEMENTS,
)


class TestAlternatives:
    def test_known_replacements(self):
        for pkg in COMMON_REPLACEMENTS:
            alts = find_alternatives(pkg)
            assert isinstance(alts, list)
            assert len(alts) > 0

    def test_toml_alternatives(self):
        alts = find_alternatives("toml")
        assert "tomli-w" in alts
        assert "tomllib" in alts

    def test_python_dateutil_alternatives(self):
        alts = find_alternatives("python-dateutil")
        assert "arrow" in alts or "pendulum" in alts or "ciso8601" in alts

    def test_seaborn_alternatives(self):
        alts = find_alternatives("seaborn")
        assert "plotly" in alts or "altair" in alts or "bokeh" in alts

    def test_unknown_package_returns_empty(self):
        alts = find_alternatives("this-is-a-fake-package-name-xyz")
        assert alts == []

    def test_add_replacement(self):
        add_replacement("test-package", ["alt1", "alt2"])
        alts = find_alternatives("test-package")
        assert "alt1" in alts
        assert "alt2" in alts

    def test_get_all_replacements(self):
        replacements = get_all_replacements()
        assert isinstance(replacements, dict)
        assert len(replacements) > 0
        assert "toml" in replacements
