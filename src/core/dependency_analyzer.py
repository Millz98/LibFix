# In src/core/dependency_analyzer.py
from datetime import datetime
from dateutil.parser import parse as parse_date
from src.data.inactive_packages import inactive_package_replacements
from packaging.version import Version

def is_potentially_inactive(package_info, package_name):  # Add package_name as an argument
    """
    Analyzes PyPI package information and checks against a curated list
    to determine if it's potentially inactive.

    Args:
        package_info (dict): The JSON response from the PyPI API for a package.
        package_name (str): The name of the package being analyzed.

    Returns:
        tuple: (bool, str, list) - True if potentially inactive, False otherwise,
               a reason string, and a list of alternatives (if available).
    """
    if package_name in inactive_package_replacements:
        inactive_data = inactive_package_replacements[package_name]
        reason = f"Known inactive package: {inactive_data.get('reason', 'No specific reason provided.')}"
        alternatives = inactive_data.get('alternatives', [])
        return True, reason, alternatives

    if not package_info or 'info' not in package_info or 'releases' not in package_info:
        return False, "Could not retrieve sufficient PyPI information.", []

    info = package_info['info']
    releases = package_info['releases']

    # Check last release date (after checking the curated list)
    latest_release_date = None
    if releases:
        try:
            # Parse all release keys as Version objects
            parsed_versions = [Version(v) for v in releases.keys() if v]
            if parsed_versions:
                latest_version_str = str(max(parsed_versions)) # Get the latest version string
                release_dates = [parse_date(r['upload_time']) for r in releases.get(latest_version_str, []) if 'upload_time' in r and r['upload_time']]
                if release_dates:
                    latest_release_date = max(release_dates)
        except Exception as e:
            print(f"Error parsing and comparing versions for {package_name}: {e}")


    if latest_release_date:
        years_since_last_release = (datetime.now() - latest_release_date).days / 365.25
        if years_since_last_release > 2:  # Example threshold: more than 2 years
            return True, f"Last release was over {years_since_last_release:.1f} years ago.", []

    # Check development status classifiers
    classifiers = info.get('classifiers', [])
    for classifier in classifiers:
        if classifier == "Development Status :: 7 - Inactive":
            return True, "Marked as 'Inactive' on PyPI.", []
        elif classifier in ["Development Status :: 6 - Mature", "Development Status :: 5 - Production/Stable"]:
            return False, "Seems to be in a mature/stable state.", []

    return False, "Seems active.", []

if __name__ == '__main__':
    # Example usage (requires internet connection)
    import requests
    import json

    package_name = "django"
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        django_info = response.json()
        inactive, reason = is_potentially_inactive(django_info)
        print(f"Django is potentially inactive: {inactive}, Reason: {reason}")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Django info: {e}")

    package_name = "aiohttp"
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        aiohttp_info = response.json()
        inactive, reason = is_potentially_inactive(aiohttp_info)
        print(f"aiohttp is potentially inactive: {inactive}, Reason: {reason}")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching aiohttp info: {e}")

    package_name = "this-package-does-not-exist"
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        non_existent_info = response.json()
        inactive, reason = is_potentially_inactive(non_existent_info)
        print(f"{package_name} is potentially inactive: {inactive}, Reason: {reason}")
    except requests.exceptions.RequestException:
        non_existent_info = None
        inactive, reason = is_potentially_inactive(non_existent_info)
        print(f"{package_name} is potentially inactive: {inactive}, Reason: {reason}")