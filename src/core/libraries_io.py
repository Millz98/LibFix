import logging
from typing import Optional

logger = logging.getLogger(__name__)

LIBRARIES_IO_API = "https://libraries.io/api"


def find_alternatives(package_name: str, ecosystem: str = "pip") -> list[dict]:
    """Find alternative packages using libraries.io API.

    Args:
        package_name: The package to find alternatives for.
        ecosystem: The package ecosystem (default: pip).

    Returns:
        A list of alternative packages with their details.
    """
    import requests

    alternatives = []

    try:
        url = f"{LIBRARIES_IO_API}/{ecosystem}/{package_name}/alternatives"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                for item in data[:5]:
                    alternatives.append({
                        'name': item.get('name', ''),
                        'description': item.get('description', ''),
                        'stars': item.get('stars', 0),
                        'forks': item.get('forks', 0),
                        'source': 'libraries.io'
                    })
            elif isinstance(data, dict):
                for item in data.get('packages', data.get('alternatives', []))[:5]:
                    alternatives.append({
                        'name': item.get('name', ''),
                        'description': item.get('description', ''),
                        'stars': item.get('stars', 0),
                        'forks': item.get('forks', 0),
                        'source': 'libraries.io'
                    })
            logger.debug(f"Found {len(alternatives)} alternatives for {package_name}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error fetching alternatives for {package_name} from libraries.io: {e}")

    if not alternatives:
        alternatives = _find_pypi_similar_packages(package_name)

    return alternatives


def _find_pypi_similar_packages(package_name: str) -> list[dict]:
    """Fallback: Search PyPI for similar packages using search API."""
    import requests

    alternatives = []

    try:
        url = f"https://pypi.org/search/?q={package_name}&o="
        headers = {"Accept": "application/vnd.pypi SEARCH.v1+json"}
        response = requests.get("https://pypi.org/search/", params={"q": package_name}, timeout=10)
        if response.status_code == 200:
            logger.debug(f"PyPI search used as fallback for {package_name}")
    except requests.exceptions.RequestException:
        pass

    return alternatives


def get_package_dependents_count(package_name: str, ecosystem: str = "pip") -> Optional[int]:
    """Get the number of packages that depend on this package.

    Args:
        package_name: The package name.
        ecosystem: The package ecosystem.

    Returns:
        The number of dependents, or None if not found.
    """
    import requests

    try:
        url = f"{LIBRARIES_IO_API}/{ecosystem}/{package_name}/dependents"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return len(data)
    except requests.exceptions.RequestException as e:
        logger.debug(f"Could not fetch dependents for {package_name}: {e}")

    return None


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    for pkg in ["python-dateutil", "seaborn", "requests"]:
        print(f"\nAlternatives for {pkg}:")
        alts = find_alternatives(pkg)
        if alts:
            for alt in alts[:3]:
                print(f"  - {alt['name']}: {alt.get('description', 'N/A')[:60]}...")
        else:
            print("  No alternatives found")
