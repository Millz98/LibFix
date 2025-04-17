# In src/core/dependency_analyzer.py
from datetime import datetime
from dateutil.parser import parse as parse_date

def is_potentially_inactive(package_info):
    """
    Analyzes PyPI package information to determine if it's potentially inactive.

    Args:
        package_info (dict): The JSON response from the PyPI API for a package.

    Returns:
        tuple: (bool, str) - True if potentially inactive, False otherwise, and a reason string.
    """
    if not package_info or 'info' not in package_info or 'releases' not in package_info:
        return False, "Could not retrieve sufficient PyPI information."

    info = package_info['info']
    releases = package_info['releases']

    # Check last release date
    latest_release_date = None
    if releases:
        # Sort versions to get the latest (basic sorting, might need more robust version parsing)
        latest_version = sorted(releases.keys(), key=lambda v: tuple(map(int, v.split('.'))))[-1]
        release_dates = [parse_date(r['upload_time']) for r in releases[latest_version] if 'upload_time' in r and r['upload_time']]
        if release_dates:
            latest_release_date = max(release_dates)

    if latest_release_date:
        years_since_last_release = (datetime.now() - latest_release_date).days / 365.25
        if years_since_last_release > 2:  # Example threshold: more than 2 years since last release
            return True, f"Last release was over {years_since_last_release:.1f} years ago."

    # Check development status classifiers
    classifiers = info.get('classifiers', [])
    for classifier in classifiers:
        if classifier == "Development Status :: 7 - Inactive":
            return True, "Marked as 'Inactive' on PyPI."
        elif classifier == "Development Status :: 6 - Mature" or \
             classifier == "Development Status :: 5 - Production/Stable":
            # If it's mature or stable, likely not inactive
            return False, "Seems to be in a mature/stable state."

    # Consider other factors like number of maintainers or project URLs in the future
    # (Access these via info.get('maintainers'), info.get('project_urls'))

    return False, "Seems active."

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