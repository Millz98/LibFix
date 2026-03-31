import pytest
from src.core.dependency_analyzer import is_potentially_inactive, INACTIVITY_THRESHOLD_YEARS


class TestDependencyAnalyzer:
    def test_threshold_is_configured(self):
        assert INACTIVITY_THRESHOLD_YEARS == 2.0

    def test_handles_none_package_info(self):
        inactive, reason, alternatives = is_potentially_inactive(None, "some-package")
        assert inactive is False
        assert "Could not retrieve" in reason

    def test_handles_missing_info(self):
        inactive, reason, alternatives = is_potentially_inactive({}, "some-package")
        assert inactive is False

    def test_inactive_package_in_replacements(self):
        from src.data.inactive_packages import inactive_package_replacements
        if inactive_package_replacements:
            first_package = next(iter(inactive_package_replacements))
            inactive, reason, alternatives = is_potentially_inactive({}, first_package)
            assert inactive is True
            assert "Known inactive" in reason
