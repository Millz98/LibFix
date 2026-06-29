"""
Package Knowledge System — dynamic learning and research for any package.

Instead of relying on hardcoded lists, this module:
1. Fetches rich metadata from PyPI (classifiers, deps, description, URLs)
2. Derives intelligence: category, ecosystem, related packages, alternatives
3. Learns co-occurrence patterns across projects
4. Caches everything persistently in ~/.libfix/knowledge/
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path.home() / ".libfix" / "knowledge"
KNOWLEDGE_FILE = KNOWLEDGE_DIR / "package-knowledge.json"
COOCCURRENCE_FILE = KNOWLEDGE_DIR / "cooccurrence.json"
KNOWLEDGE_VERSION = 1


def _ensure_dir() -> None:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Knowledge store (persistent JSON)
# ---------------------------------------------------------------------------

class PackageKnowledge:
    """Rich, learned information about a single package."""

    def __init__(self, data: dict = None):
        data = data or {}
        self.name: str = data.get("name", "")
        self.version: str = data.get("version", "")
        self.summary: str = data.get("summary", "")
        self.description: str = data.get("description", "")[:500]
        self.author: str = data.get("author", "")
        self.license: str = data.get("license", "")
        self.home_page: str = data.get("home_page", "")
        self.project_urls: dict = data.get("project_urls", {})
        self.classifiers: list[str] = data.get("classifiers", [])
        self.keywords: list[str] = data.get("keywords", "").split() if isinstance(data.get("keywords"), str) else data.get("keywords", [])
        self.requires_dist: list[str] = data.get("requires_dist", [])
        self.requires_python: str = data.get("requires_python", "")

        # Derived intelligence
        self.category: str = data.get("category", "unknown")  # web, cli, testing, data, etc.
        self.ecosystem: str = data.get("ecosystem", "general")  # django, flask, fastapi, data-science, etc.
        self.related_packages: list[str] = data.get("related_packages", [])
        self.alternatives: list[str] = data.get("alternatives", [])
        self.is_obsolete: bool = data.get("is_obsolete", False)
        self.replaced_by: str = data.get("replaced_by", "")
        self.is_actively_maintained: bool = data.get("is_actively_maintained", True)

        # Learning metadata
        self.times_seen: int = data.get("times_seen", 1)
        self.first_seen: str = data.get("first_seen", datetime.now().isoformat())
        self.last_seen: str = data.get("last_seen", datetime.now().isoformat())
        self.last_refreshed: str = data.get("last_refreshed", "")

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    @classmethod
    def from_pypi_metadata(cls, pypi_data: dict) -> "PackageKnowledge":
        """Create rich knowledge from raw PyPI JSON metadata."""
        info = pypi_data.get("info", pypi_data)
        name = info.get("name", "")

        classifiers = info.get("classifiers", [])
        keywords_raw = info.get("keywords", "")
        keywords = keywords_raw.split() if isinstance(keywords_raw, str) else keywords_raw or []
        summary = info.get("summary", "") or ""
        description = info.get("description", "") or ""

        # Derive category from classifiers and keywords
        category = _derive_category(classifiers, keywords, summary, description)
        ecosystem = _derive_ecosystem(classifiers, keywords, summary, name)
        alternatives = _derive_alternatives(classifiers, keywords, summary, description, name)
        related = _derive_related(info.get("requires_dist", []))

        # Determine maintenance status
        last_version = info.get("version", "")
        is_maintained = _check_maintenance(classifiers, pypi_data)

        return cls(data={
            "name": name,
            "version": last_version,
            "summary": summary,
            "description": description,
            "author": info.get("author", "") or "",
            "license": info.get("license", "") or info.get("license_expression", ""),
            "home_page": info.get("home_page", "") or "",
            "project_urls": info.get("project_urls", {}) or {},
            "classifiers": classifiers[:20],
            "keywords": keywords[:20],
            "requires_dist": _extract_package_names(info.get("requires_dist", [])),
            "requires_python": info.get("requires_python", ""),
            "category": category,
            "ecosystem": ecosystem,
            "related_packages": related,
            "alternatives": alternatives,
            "is_actively_maintained": is_maintained,
            "last_refreshed": datetime.now().isoformat(),
        })


# ---------------------------------------------------------------------------
# Co-occurrence learning
# ---------------------------------------------------------------------------

class CooccurrenceStore:
    """Tracks which packages appear together across scans."""

    def __init__(self, data: dict = None):
        self.data = data or {}  # {pkg: {co_pkg: count}}

    def record(self, packages: list[str]) -> None:
        """Record that these packages appeared together."""
        normalized = [p.lower().replace("-", "_") for p in packages]
        for pkg in normalized:
            if pkg not in self.data:
                self.data[pkg] = {}
            for other in normalized:
                if other != pkg:
                    self.data[pkg][other] = self.data[pkg].get(other, 0) + 1

    def get_related(self, package_name: str, top_n: int = 5) -> list[str]:
        """Get packages that commonly appear with this one."""
        normalized = package_name.lower().replace("-", "_")
        if normalized not in self.data:
            return []
        co = self.data[normalized]
        sorted_co = sorted(co.items(), key=lambda x: x[1], reverse=True)
        return [pkg for pkg, count in sorted_co[:top_n]]


# ---------------------------------------------------------------------------
# Intelligence derivation (rule-based analysis of metadata)
# ---------------------------------------------------------------------------

CATEGORY_RULES = [
    (["web", "http", "wsgi", "rest", "api", "cgi", "websocket", "server", "client"], "web"),
    (["test", "mock", "fixture", "pytest", "unittest", "coverage", "fuzz"], "testing"),
    (["database", "sql", "orm", "db", "mysql", "postgres", "mongo", "redis", "sqlite"], "database"),
    (["cli", "command.line", "terminal", "console", "argparse", "click"], "cli"),
    (["data", "csv", "pandas", "numpy", "dataframe", "analysis", "science", "plot"], "data-science"),
    (["auth", "login", "jwt", "oauth", "security", "crypt", "password", "encryption"], "security"),
    (["image", "pillow", "photo", "graphic", "svg", "png", "opencv"], "imaging"),
    (["network", "socket", "tcp", "udp", "ssh", "ftp", "ssl", "tls"], "networking"),
    (["gui", "tkinter", "qt", "gtk", "wx", "widget", "desktop", "ui"], "gui"),
    (["async", "asyncio", "twisted", "trio", "aio"], "async"),
    (["log", "logging", "logstash", "sentry"], "logging"),
    (["serialize", "json", "xml", "yaml", "toml", "msgpack", "protobuf"], "serialization"),
    (["template", "jinja", "mako", "mustache", "render"], "templating"),
    (["cache", "memcache", "redis", "lru"], "caching"),
    (["task", "queue", "celery", "rq", "worker", "job", "schedule"], "task-queue"),
    (["doc", "sphinx", "mkdocs", "readme", "documentation"], "documentation"),
    (["package", "setuptools", "pip", "build", "distribute", "wheel", "packaging"], "packaging"),
    (["debug", "trace", "profile", "debugger", "inspect"], "debugging"),
]

ECOSYSTEM_RULES = [
    (["django", "wagtail", "channels", "rest_framework"], "django"),
    (["flask", "werkzeug", "jinja2", "click", "itsdangerous"], "flask"),
    (["fastapi", "starlette", "pydantic", "uvicorn"], "fastapi"),
    (["numpy", "scipy", "pandas", "matplotlib", "sklearn", "scikit"], "data-science"),
    (["torch", "tensorflow", "keras", "jax", "pytorch"], "ml"),
    (["pytest", "hypothesis", "faker", "factory_boy"], "testing"),
    (["requests", "httpx", "aiohttp", "urllib3"], "http"),
    (["sqlalchemy", "alembic", "peewee"], "orm"),
    (["celery", "redis", "kombu"], "task-queue"),
    (["pillow", "opencv", "imageio"], "imaging"),
    (["sphinx", "mkdocs", "docutils"], "docs"),
    (["click", "typer", "argparse", "fire"], "cli"),
    (["boto3", "botocore", "aws"], "aws"),
    (["google", "gcp", "firebase"], "gcp"),
    (["azure", "msal"], "azure"),
]

# Known alternatives discovered from package metadata
ALTERNATIVE_PATTERNS = {
    "requests": ["httpx", "aiohttp", "urllib3"],
    "httpx": ["requests", "aiohttp"],
    "flask": ["fastapi", "django", "bottle", "starlette"],
    "django": ["flask", "fastapi", "pyramid"],
    "fastapi": ["flask", "django", "starlette"],
    "sqlalchemy": ["peewee", "tortoise-orm", "pony"],
    "psycopg2": ["psycopg[binary]", "asyncpg", "pg8000"],
    "pytest": ["unittest", "nose2", "robot"],
    "unittest": ["pytest"],
    "pillow": ["opencv-python", "imageio"],
    "celery": ["rq", "huey", "dramatiq"],
    "jinja2": ["mako", "chameleon"],
    "pyyaml": ["ruamel.yaml", "omegaconf"],
    "configparser": ["toml", "pyyaml"],
    "argparse": ["click", "typer", "docopt", "fire"],
    "click": ["typer", "argparse", "fire"],
    "boto3": ["libcloud"],
    "paramiko": ["fabric", "asyncssh"],
    "fabric": ["paramiko", "invoke"],
    "nose": ["pytest"],
    "nose2": ["pytest"],
    "mock": ["pytest-mock", "responses", "mocket"],
    "simplejson": ["orjson", "ujson", "msgspec"],
    "ujson": ["orjson", "msgspec", "simplejson"],
    "orjson": ["ujson", "msgspec", "simplejson"],
    "python-dateutil": ["arrow", "pendulum", "maya"],
    "werkzeug": ["werkzeug"],
    "itsdangerous": ["itsdangerous"],
    "gunicorn": ["uvicorn", "waitress", "hypercorn"],
    "uvicorn": ["gunicorn", "hypercorn", "daphne"],
    "aiohttp": ["httpx", "trio-websocket"],
    "trio": ["asyncio", "anyio"],
    "anyio": ["trio", "asyncio"],
    "coverage": ["pytest-cov", "codecov"],
    "flake8": ["ruff", "pylint"],
    "pylint": ["ruff", "flake8", "pyright"],
    "ruff": ["flake8", "pylint"],
    "black": ["ruff", "yapf", "autopep8"],
    "isort": ["ruff"],
    "mypy": ["pyright", "pytype"],
    "pyright": ["mypy"],
    "sphinx": ["mkdocs", "pdoc"],
    "mkdocs": ["sphinx"],
    "docker": ["podman"],
    "kubernetes": ["k3s"],
    "elasticsearch": ["opensearch-py", "solr"],
    "kombu": ["redis"],
    "lxml": ["beautifulsoup4", "html5lib"],
    "beautifulsoup4": ["lxml", "pyquery", "parsel"],
    "scrapy": ["beautifulsoup4", "selenium", "playwright"],
    "selenium": ["playwright", "splinter", "mechanize"],
    "playwright": ["selenium"],
    "matplotlib": ["seaborn", "plotly", "bokeh", "altair"],
    "seaborn": ["matplotlib", "plotly", "bokeh"],
    "plotly": ["matplotlib", "seaborn", "bokeh", "altair"],
    "tensorflow": ["pytorch", "jax", "keras"],
    "torch": ["tensorflow", "jax"],
    "opencv-python": ["pillow", "imageio", "scikit-image"],
    "scikit-learn": ["tensorflow", "pytorch", "xgboost"],
    "xgboost": ["lightgbm", "catboost", "scikit-learn"],
    "lightgbm": ["xgboost", "catboost"],
    "pip": ["uv", "poetry", "pipenv", "pdm"],
    "poetry": ["pip", "uv", "pdm", "pipenv"],
    "uv": ["pip", "poetry"],
    "pipenv": ["poetry", "pip", "pdm"],
    "setuptools": ["flit", "hatchling", "poetry-core"],
    "wheel": ["flit"],
    "twine": ["flit"],
    "tox": ["nox", "pre-commit"],
    "nox": ["tox"],
    "pre-commit": ["tox"],
    "responses": ["httpretty", "vcrpy", "mocket"],
    "vcrpy": ["responses"],
    "freezegun": ["time-machine", "delorean"],
    "time-machine": ["freezegun"],
    "faker": ["factory_boy", "mimesis"],
    "factory_boy": ["faker", "model_bakery"],
    "marshmallow": ["pydantic", "attrs", "dataclasses"],
    "pydantic": ["marshmallow", "attrs", "dataclasses", "attrs"],
    "attrs": ["pydantic", "dataclasses", "marshmallow"],
    "cerberus": ["pydantic", "marshmallow"],
    "jsonschema": ["pydantic", "cerberus"],
    "cryptography": ["pycryptodome", "pynacl"],
    "pycryptodome": ["cryptography"],
    "bcrypt": ["argon2-cffi", "passlib"],
    "passlib": ["bcrypt", "argon2-cffi"],
    "python-jose": ["pyjwt", "authlib"],
    "pyjwt": ["python-jose", "authlib"],
    "authlib": ["pyjwt", "python-jose"],
}


def _derive_category(classifiers: list[str], keywords: list[str], summary: str, description: str) -> str:
    """Determine package category from metadata."""
    text = " ".join(classifiers + keywords + [summary, description]).lower()

    for patterns, category in CATEGORY_RULES:
        for pattern in patterns:
            if pattern in text:
                return category

    # Check classifiers for framework hints
    for c in classifiers:
        c_lower = c.lower()
        if "framework" in c_lower:
            for fw in ["django", "flask", "fastapi", "pyramid", "tornado", "bottle", "aiohttp", "sanic"]:
                if fw in c_lower:
                    return "web"

    return "general"


def _derive_ecosystem(classifiers: list[str], keywords: list[str], summary: str, name: str) -> str:
    """Determine which ecosystem a package belongs to."""
    text = " ".join(classifiers + keywords + [summary, name]).lower()

    for patterns, ecosystem in ECOSYSTEM_RULES:
        for pattern in patterns:
            if pattern in text:
                return ecosystem

    return "general"


def _derive_alternatives(classifiers: list[str], keywords: list[str], summary: str, description: str, name: str) -> list[str]:
    """Find alternative packages based on metadata and known patterns."""
    normalized = name.lower().replace("-", "_")

    # Check known alternatives first
    if normalized in ALTERNATIVE_PATTERNS:
        return ALTERNATIVE_PATTERNS[normalized]

    # Try to infer from category
    text = " ".join(classifiers + keywords + [summary, description]).lower()
    category = _derive_category(classifiers, keywords, summary, description)

    # Find other packages in the same category that might be alternatives
    alternatives = []
    for pkg_name, alts in ALTERNATIVE_PATTERNS.items():
        pkg_cat = _derive_category([], [], "", "")
        # Check if any of this package's alternatives share the same category
        if name.lower() in [a.lower() for a in alts]:
            alternatives.append(pkg_name)

    return alternatives[:5]


def _derive_related(requires_dist: list[str]) -> list[str]:
    """Extract package names from requires_dist for relationship mapping."""
    return _extract_package_names(requires_dist[:10])


def _extract_package_names(requires_dist: list) -> list[str]:
    """Extract clean package names from PEP 508 requirement strings."""
    packages = []
    for req in requires_dist:
        if not isinstance(req, str):
            continue
        # Handle extras like "package[extra]>=1.0; extra == 'dev'"
        req = req.split(";")[0].strip()
        match = re.match(r"^([a-zA-Z0-9_-]+)", req)
        if match:
            pkg = match.group(1).lower()
            if pkg not in packages:
                packages.append(pkg)
    return packages


def _check_maintenance(classifiers: list[str], pypi_data: dict) -> bool:
    """Heuristically determine if a package is actively maintained."""
    # Check development status classifier
    for c in classifiers:
        c_lower = c.lower()
        if "development status :: 7 - inactive" in c_lower:
            return False
        if "development status :: 1 - planning" in c_lower:
            return False
        if "development status :: 4 - beta" in c_lower:
            return False  # might still be active but uncertain

    # Check if there's a recent release
    urls = pypi_data.get("urls", [])
    if urls:
        # If there are release URLs, there's been at least one release
        pass

    return True


# ---------------------------------------------------------------------------
# Knowledge Manager (main interface)
# ---------------------------------------------------------------------------

class KnowledgeManager:
    """Manages the persistent knowledge base for all packages."""

    def __init__(self):
        self.packages: dict[str, PackageKnowledge] = {}
        self.cooccurrence = CooccurrenceStore()
        self._load()

    def _load(self) -> None:
        _ensure_dir()
        if KNOWLEDGE_FILE.exists():
            try:
                with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for pkg_name, pkg_data in data.get("packages", {}).items():
                    self.packages[pkg_name.lower()] = PackageKnowledge(pkg_data)
                logger.debug(f"Loaded knowledge for {len(self.packages)} packages")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load knowledge file: {e}")

        if COOCCURRENCE_FILE.exists():
            try:
                with open(COOCCURRENCE_FILE, "r", encoding="utf-8") as f:
                    co_data = json.load(f)
                self.cooccurrence = CooccurrenceStore(co_data)
            except (json.JSONDecodeError, IOError):
                pass

    def save(self) -> None:
        _ensure_dir()
        data = {
            "version": KNOWLEDGE_VERSION,
            "last_updated": datetime.now().isoformat(),
            "packages": {name: pkg.to_dict() for name, pkg in self.packages.items()},
        }
        try:
            with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error(f"Could not save knowledge file: {e}")

        try:
            with open(COOCCURRENCE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cooccurrence.data, f, indent=2)
        except IOError as e:
            logger.error(f"Could not save cooccurrence file: {e}")

    def learn_package(self, pypi_data: dict) -> PackageKnowledge:
        """Learn about a package from PyPI metadata."""
        pkg = PackageKnowledge.from_pypi_metadata(pypi_data)
        key = pkg.name.lower()

        if key in self.packages:
            # Update existing knowledge
            existing = self.packages[key]
            existing.version = pkg.version or existing.version
            existing.summary = pkg.summary or existing.summary
            existing.times_seen += 1
            existing.last_seen = datetime.now().isoformat()
            existing.last_refreshed = datetime.now().isoformat()
            # Merge alternatives
            for alt in pkg.alternatives:
                if alt not in existing.alternatives:
                    existing.alternatives.append(alt)
            self.packages[key] = existing
        else:
            self.packages[key] = pkg

        return self.packages[key]

    def get_knowledge(self, package_name: str) -> Optional[PackageKnowledge]:
        """Get knowledge about a package."""
        return self.packages.get(package_name.lower())

    def record_cooccurrence(self, packages: list[str]) -> None:
        """Record that these packages appeared together."""
        self.cooccurrence.record(packages)

    def get_alternatives(self, package_name: str) -> list[str]:
        """Get alternatives for a package, combining known + learned data."""
        normalized = package_name.lower().replace("-", "_")
        alternatives = []

        # From direct knowledge
        if normalized in ALTERNATIVE_PATTERNS:
            alternatives.extend(ALTERNATIVE_PATTERNS[normalized])

        # From learned knowledge
        knowledge = self.get_knowledge(package_name)
        if knowledge:
            for alt in knowledge.alternatives:
                if alt not in alternatives:
                    alternatives.append(alt)

        # From co-occurrence (packages that often appear together)
        co_related = self.cooccurrence.get_related(package_name, top_n=3)
        for pkg in co_related:
            if pkg not in alternatives and pkg != normalized:
                alternatives.append(pkg)

        return alternatives[:8]

    def get_category(self, package_name: str) -> str:
        """Get the category of a package."""
        knowledge = self.get_knowledge(package_name)
        if knowledge:
            return knowledge.category
        return "unknown"

    def get_ecosystem(self, package_name: str) -> str:
        """Get the ecosystem of a package."""
        knowledge = self.get_knowledge(package_name)
        if knowledge:
            return knowledge.ecosystem
        return "general"

    def is_actively_maintained(self, package_name: str) -> bool:
        """Check if a package appears to be actively maintained."""
        knowledge = self.get_knowledge(package_name)
        if knowledge:
            return knowledge.is_actively_maintained
        return True  # assume maintained if unknown

    def get_summary(self, package_name: str) -> str:
        """Get a human-readable summary of a package."""
        knowledge = self.get_knowledge(package_name)
        if knowledge:
            return knowledge.summary
        return ""

    def get_all_categories(self) -> dict[str, list[str]]:
        """Get all packages grouped by category."""
        categories: dict[str, list[str]] = {}
        for name, pkg in self.packages.items():
            cat = pkg.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(name)
        return categories


# Singleton instance
_knowledge_manager: Optional[KnowledgeManager] = None


def get_knowledge_manager() -> KnowledgeManager:
    """Get the global knowledge manager singleton."""
    global _knowledge_manager
    if _knowledge_manager is None:
        _knowledge_manager = KnowledgeManager()
    return _knowledge_manager


def learn_from_pypi(package_name: str, pypi_data: dict) -> PackageKnowledge:
    """Learn about a package from PyPI data and persist it."""
    km = get_knowledge_manager()
    knowledge = km.learn_package(pypi_data)
    km.save()
    return knowledge


def get_package_alternatives(package_name: str) -> list[str]:
    """Get alternatives for a package using all available knowledge."""
    km = get_knowledge_manager()
    return km.get_alternatives(package_name)


def get_package_category(package_name: str) -> str:
    """Get the category of a package."""
    km = get_knowledge_manager()
    return km.get_category(package_name)


def record_project_packages(packages: list[str]) -> None:
    """Record co-occurrence of packages from a project scan."""
    km = get_knowledge_manager()
    km.record_cooccurrence(packages)
    km.save()
