import logging
from typing import Optional

logger = logging.getLogger(__name__)

INACTIVITY_THRESHOLD_YEARS: float = 2.0


def set_threshold(years: float) -> None:
    """Set the global inactivity threshold (useful for CLI)."""
    global INACTIVITY_THRESHOLD_YEARS
    INACTIVITY_THRESHOLD_YEARS = years


def is_potentially_inactive(
    package_info: Optional[dict],
    package_name: str,
    threshold: float = INACTIVITY_THRESHOLD_YEARS,
    find_alternatives: bool = True
) -> tuple[bool, str, list[str]]:
    """Analyzes PyPI package information to determine if it's potentially inactive.

    Args:
        package_info: The JSON response from the PyPI API for a package.
        package_name: The name of the package being analyzed.
        threshold: Years since last release to consider inactive (default: 2.0).
        find_alternatives: Whether to search for alternatives for inactive packages.

    Returns:
        A tuple of (is_inactive: bool, reason: str, alternatives: list[str]).
    """
    from src.data.inactive_packages import inactive_package_replacements

    if package_name in inactive_package_replacements:
        inactive_data = inactive_package_replacements[package_name]
        reason = f"Known inactive package: {inactive_data.get('reason', 'No specific reason provided.')}"
        alternatives = inactive_data.get('alternatives', [])
        logger.debug(f"Package '{package_name}' is in inactive replacements list")
        return True, reason, alternatives

    if not package_info or 'info' not in package_info or 'releases' not in package_info:
        return False, "Could not retrieve sufficient PyPI information.", []

    info = package_info['info']
    releases = package_info['releases']

    latest_release_date = None
    if releases:
        try:
            from dateutil.parser import parse as parse_date
            from packaging.version import Version

            parsed_versions = [Version(v) for v in releases.keys() if v]
            if parsed_versions:
                latest_version_str = str(max(parsed_versions))
                release_dates = [
                    parse_date(r['upload_time'])
                    for r in releases.get(latest_version_str, [])
                    if 'upload_time' in r and r['upload_time']
                ]
                if release_dates:
                    latest_release_date = max(release_dates)
        except Exception:
            pass

    if latest_release_date:
        from datetime import datetime
        years_since_last_release = (datetime.now() - latest_release_date).days / 365.25
        if years_since_last_release > threshold:
            alternatives = []
            if find_alternatives:
                alternatives = _find_alternatives_for_package(package_name, package_info)
            return True, f"Last release was over {years_since_last_release:.1f} years ago.", alternatives

    classifiers = info.get('classifiers', [])
    for classifier in classifiers:
        if classifier == "Development Status :: 7 - Inactive":
            alternatives = []
            if find_alternatives:
                alternatives = _find_alternatives_for_package(package_name, package_info)
            return True, "Marked as 'Inactive' on PyPI.", alternatives
        elif classifier in ["Development Status :: 6 - Mature", "Development Status :: 5 - Production/Stable"]:
            return False, "Seems to be in a mature/stable state.", []

    return False, "Seems active.", []


def _find_alternatives_for_package(package_name: str, package_info: Optional[dict] = None) -> list[str]:
    """Find alternative packages for an inactive package.

    Args:
        package_name: The name of the inactive package.
        package_info: Optional PyPI package info for context.

    Returns:
        A list of alternative package names.
    """
    from src.core.alternatives import find_alternatives

    try:
        alts = find_alternatives(package_name, package_info)
        if alts:
            logger.info(f"Found alternatives for {package_name}: {alts}")
            return alts[:3]
    except Exception as e:
        logger.warning(f"Error finding alternatives for {package_name}: {e}")

    return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    import requests

    for package_name in ["python-dateutil", "seaborn", "requests"]:
        url = f"https://pypi.org/pypi/{package_name}/json"
        try:
            response = requests.get(url)
            response.raise_for_status()
            package_info = response.json()
        except requests.exceptions.RequestException:
            package_info = None
        inactive, reason, alts = is_potentially_inactive(package_info, package_name)
        print(f"\n{package_name}: inactive={inactive}")
        print(f"  Reason: {reason}")
        if alts:
            print(f"  Alternatives: {', '.join(alts)}")
