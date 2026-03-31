import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_package_info_from_pypi(package_name: str, use_cache: bool = True) -> Optional[dict]:
    """Fetches package information from the PyPI JSON API.

    Args:
        package_name: The name of the package.
        use_cache: Whether to use cached results.

    Returns:
        A dictionary containing the package information if successful,
        None if there was an error.
    """
    import requests

    if use_cache:
        from .cache import get_cache
        cache = get_cache()
        cached = cache.get(package_name)
        if cached is not None:
            return cached

    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if use_cache:
            cache.set(package_name, data)
        logger.debug(f"Successfully fetched info for {package_name}")
        return data
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Package '{package_name}' not found on PyPI: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching '{package_name}': {e}")
        return None


def clear_cache() -> None:
    """Clears the package cache."""
    from .cache import get_cache
    get_cache().clear()


if __name__ == "__main__":
    import json
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Fetch package info from PyPI")
    parser.add_argument("package", help="Package name to look up")
    parser.add_argument("--no-cache", action="store_true", help="Skip cache")
    args = parser.parse_args()

    info = get_package_info_from_pypi(args.package, use_cache=not args.no_cache)
    if info:
        print(json.dumps(info, indent=2))
    else:
        print(f"Could not retrieve information for {args.package}.")
