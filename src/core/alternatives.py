import logging
from typing import Optional

logger = logging.getLogger(__name__)

ALTERNATIVES_CACHE: dict[str, list[str]] = {}

COMMON_REPLACEMENTS: dict[str, list[str]] = {
    "toml": ["tomli-w", "tomllib"],
    "python-dateutil": ["arrow", "pendulum", "ciso8601"],
    "seaborn": ["plotly", "altair", "bokeh"],
    "nose": ["pytest", "unittest"],
    "nose2": ["pytest"],
    "mock": ["pytest-mock", "unittest.mock"],
    "pandas-datareader": ["yfinance", "investpy", "alpha-vantage"],
    "matplotlib-venn": ["matplotlib"],
    "scikit-learn": ["sklearn"],
    "Pillow": ["PIL"],
    "opencv-python": ["opencv-python-headless"],
    "PyYAML": ["ruamel.yaml"],
    "python-jose": ["PyJWT", "python-jose[cryptography]"],
    "boto3": ["aioboto3"],
    "aiohttp": ["httpx", "aiofiles"],
    "ujson": ["orjson", "msgspec"],
    "ujson": ["orjson"],
    "flask-cors": ["flask[crossdomain]"],
    "django-cors-headers": ["django-cors-headers"],
    "python-dateutil": ["ciso8601", "pendulum"],
    "pytz": ["zoneinfo", "timezone"],
    "texttable": ["tabulate", "prettytable"],
    "configparser": ["python-dotenv"],
    "redis-py": ["redis"],
    "mysql-connector-python": ["pymysql", "aiomysql"],
    "psycopg2": ["psycopg[binary]", "asyncpg"],
    "ujson": ["orjson", "msgspec"],
    "yaml": ["ruamel.yaml"],
    "simplejson": ["orjson"],
    "requests-oauthlib": ["authlib"],
    "chardet": ["charset-normalizer"],
    "html5-parser": ["lxml", "beautifulsoup4"],
    "bleach": ["sanitize-html", "markupsafe"],
    "pillow": ["Pillow"],
    "ipython": ["jupyter"],
}


def find_alternatives(package_name: str, package_info: Optional[dict] = None) -> list[str]:
    """Find alternative packages for a given package.

    Args:
        package_name: The package to find alternatives for.
        package_info: Optional PyPI package info for context.

    Returns:
        A list of alternative package names.
    """
    if package_name in ALTERNATIVES_CACHE:
        return ALTERNATIVES_CACHE[package_name]

    alternatives = []

    if package_name in COMMON_REPLACEMENTS:
        alternatives = COMMON_REPLACEMENTS[package_name].copy()
        logger.debug(f"Found common replacement for {package_name}: {alternatives}")

    if not alternatives and package_info:
        alternatives = _search_pypi_related(package_name, package_info)

    ALTERNATIVES_CACHE[package_name] = alternatives
    return alternatives


def _search_pypi_related(package_name: str, package_info: dict) -> list[str]:
    """Search PyPI for related packages based on keywords."""
    import requests

    try:
        info = package_info.get('info', {})
        keywords = info.get('keywords', '') or ''
        summary = info.get('summary', '') or ''
        name_parts = package_name.lower().replace('-', ' ').replace('_', ' ').split()

        search_terms = keywords.split(',')[:3] + [package_name.replace('-', '')]
        search_terms = [t.strip() for t in search_terms if t and len(t) > 2]

        if not search_terms:
            return []

        search_url = "https://pypi.org/search/"
        response = requests.get(search_url, params={'q': ' '.join(search_terms[:2])}, timeout=10)

        if response.status_code == 200:
            logger.debug(f"Searched PyPI for alternatives to {package_name}")

    except requests.exceptions.RequestException as e:
        logger.debug(f"Could not search PyPI for {package_name}: {e}")

    return []


def add_replacement(original: str, alternatives: list[str]) -> None:
    """Add a custom replacement mapping.

    Args:
        original: The original package name.
        alternatives: List of alternative package names.
    """
    COMMON_REPLACEMENTS[original.lower()] = alternatives
    ALTERNATIVES_CACHE[original.lower()] = alternatives


def get_all_replacements() -> dict[str, list[str]]:
    """Get all known replacements."""
    return COMMON_REPLACEMENTS.copy()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    test_packages = ["toml", "python-dateutil", "seaborn", "requests", "pytest", "flask"]

    print("\nAlternative packages suggestions:")
    print("=" * 50)
    for pkg in test_packages:
        alts = find_alternatives(pkg)
        if alts:
            print(f"{pkg}: -> {', '.join(alts)}")
        else:
            print(f"{pkg}: No known alternatives")
