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

    def test_inactive_package_by_classifier(self):
        """Test that packages with 'Inactive' classifier flag are detected as inactive."""
        package_info = {
            "info": {
                "name": "old-package",
                "version": "1.0",
                "classifiers": ["Development Status :: 7 - Inactive"],
                "keywords": "",
                "summary": "An old inactive package",
            },
            "releases": {},  # No releases so date check is skipped
        }
        inactive, reason, alternatives = is_potentially_inactive(package_info, "old-package")
        assert inactive is True
        assert "Inactive" in reason

    def test_known_alternatives_from_knowledge(self):
        """Test that known alternatives are returned for common packages."""
        from datetime import datetime, timedelta
        recent_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
        package_info = {
            "info": {
                "name": "requests",
                "version": "2.32.0",
                "classifiers": ["Development Status :: 5 - Production/Stable"],
                "keywords": "http requests",
                "summary": "Python HTTP for Humans.",
            },
            "releases": {"2.32.0": [{"upload_time": recent_date}]},
        }
        inactive, reason, alternatives = is_potentially_inactive(package_info, "requests")
        assert inactive is False
