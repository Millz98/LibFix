import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MigrationHint:
    old_pattern: str
    new_pattern: str
    file_path: str
    line_number: int
    line_content: str
    note: str


@dataclass
class MigrationGuide:
    old_package: str
    new_package: str
    general_notes: list[str] = field(default_factory=list)
    hints: list[MigrationHint] = field(default_factory=list)


@dataclass
class ReplacementPattern:
    old: str
    new: str
    note: str = ""


MIGRATION_GUIDES: dict[str, dict] = {
    "toml": {
        "new": "tomllib",
        "import_map": {
            "import toml": "import tomllib",
            "from toml import": "from tomllib import",
        },
        "replacements": [
            ("open('config.toml', 'r')", "open('config.toml', 'rb')", "tomllib requires binary mode"),
            ("open(file, 'r')", "open(file, 'rb')", "tomllib requires binary mode"),
            ("toml.load(", "tomllib.load("),
            ("toml.dump(", "tomllib.dump("),
            ("toml.loads(", "tomllib.loads("),
            ("toml.dumps(", "tomllib.dumps("),
        ],
        "notes": [
            "tomllib is built into Python 3.11+",
            "tomllib.load() requires a binary file object ('rb' mode)",
            "tomllib.loads() works with strings",
        ],
        "example_old": "with open('config.toml', 'r') as f:\n    config = toml.load(f)",
        "example_new": "with open('config.toml', 'rb') as f:\n    config = tomllib.load(f)",
    },
    "python-dateutil": {
        "new": "pendulum",
        "import_map": {
            "from dateutil import parser": "import pendulum",
            "import dateutil": "import pendulum",
            "from dateutil.parser import parse": "import pendulum",
        },
        "replacements": [
            ("dateutil.parser.parse(", "pendulum.parse("),
            ("parser.parse(", "pendulum.parse("),
            ("from dateutil import relativedelta", "from pendulum import Duration"),
            ("relativedelta(", "Duration("),
            ("dateutil.relativedelta(", "pendulum.duration("),
        ],
        "notes": [
            "pendulum is a drop-in replacement for dateutil",
            "parse() is API-compatible with dateutil.parser.parse()",
        ],
        "example_old": "from dateutil import parser\ndt = parser.parse('2024-01-15')",
        "example_new": "import pendulum\ndt = pendulum.parse('2024-01-15')",
    },
    "pytz": {
        "new": "zoneinfo",
        "import_map": {
            "import pytz": "from zoneinfo import ZoneInfo",
            "from pytz import timezone": "from zoneinfo import ZoneInfo",
            "from pytz import utc": "from zoneinfo import UTC",
        },
        "replacements": [
            ("pytz.timezone(", "ZoneInfo("),
            ("pytz.utc", "UTC"),
            ("timezone('UTC')", "UTC"),
            ("pytz.timezone('UTC')", "UTC"),
            (".astimezone(pytz.utc)", ".astimezone(UTC)"),
            (".replace(tzinfo=pytz.utc)", ".replace(tzinfo=UTC)"),
        ],
        "notes": [
            "zoneinfo is built into Python 3.9+",
            "No installation needed",
            "Use ZoneInfo('US/Eastern') instead of pytz.timezone('US/Eastern')",
        ],
        "example_old": "import pytz\ntz = pytz.timezone('US/Eastern')\ndt = datetime(2024, 1, 1, tzinfo=tz)",
        "example_new": "from zoneinfo import ZoneInfo\ntz = ZoneInfo('US/Eastern')\ndt = datetime(2024, 1, 1, tzinfo=tz)",
    },
    "seaborn": {
        "new": "plotly",
        "import_map": {
            "import seaborn": "import plotly.express as px",
            "import seaborn as sns": "import plotly.express as px",
        },
        "replacements": [
            ("sns.", "px."),
            ("sns.lineplot(", "px.line("),
            ("sns.scatterplot(", "px.scatter("),
            ("sns.barplot(", "px.bar("),
            ("sns.histplot(", "px.histogram("),
            ("sns.boxplot(", "px.box("),
            ("sns.heatmap(", "px.imshow("),
            ("sns.distplot(", "px.histogram("),
            ("sns.pairplot(", "px.scatter_matrix("),
            ("sns.catplot(", "px.box("),
            ("sns.countplot(", "px.histogram("),
            ("sns.violinplot(", "px.violin("),
            ("sns.regplot(", "px.scatter("),
            ("sns.relplot(", "px.scatter("),
            ("sns.factorplot(", "px.box("),
            ("sns.jointplot(", "px.density_contour("),
            (", data=", ", x=, y="),
            (".set_title(", ".update_layout(title="),
            (".set_xlabel(", ".update_layout(xaxis_title="),
            (".set_ylabel(", ".update_layout(yaxis_title="),
            (".legend()", ""),
        ],
        "notes": [
            "plotly.express has a different API than seaborn",
            "Key differences: data=df becomes x=df['col'], y=df['col']",
            "Plot customization uses .update_layout() instead of .set_title()",
        ],
        "example_old": "import seaborn as sns\nsns.lineplot(data=df, x='time', y='value')",
        "example_new": "import plotly.express as px\npx.line(df, x='time', y='value')",
    },
    "mock": {
        "new": "unittest.mock",
        "import_map": {
            "from mock import": "from unittest.mock import",
            "import mock": "from unittest import mock",
        },
        "replacements": [
            ("from mock import", "from unittest.mock import"),
            ("import mock", "from unittest import mock"),
            ("Mock()", "MagicMock()"),
            ("mock.patch", "unittest.mock.patch"),
            ("@mock.patch", "@unittest.mock.patch"),
            ("@mock.create_autospec", "@unittest.mock.create_autospec"),
        ],
        "notes": [
            "unittest.mock is built into Python 3.3+",
            "Use MagicMock() instead of Mock() for callable mocks",
        ],
    },
    "ujson": {
        "new": "orjson",
        "import_map": {
            "import ujson": "import orjson",
        },
        "replacements": [
            ("import ujson", "import orjson"),
            ("ujson.dumps(", "orjson.dumps("),
            ("ujson.loads(", "orjson.loads("),
        ],
        "notes": [
            "orjson.dumps() returns bytes, not str",
            "Use .decode() if you need a string: orjson.dumps(data).decode()",
        ],
        "example_old": "data = ujson.dumps({'key': 'value'})",
        "example_new": "data = orjson.dumps({'key': 'value'}).decode()",
    },
    "requests": {
        "new": "httpx",
        "import_map": {
            "import requests": "import httpx",
        },
        "replacements": [
            ("requests.get(", "httpx.get("),
            ("requests.post(", "httpx.post("),
            ("requests.put(", "httpx.put("),
            ("requests.delete(", "httpx.delete("),
            ("requests.patch(", "httpx.patch("),
            ("requests.head(", "httpx.head("),
            ("requests.options(", "httpx.options("),
            (".status_code", ".status_code"),
            (".json()", ".json()"),
            (".text", ".text"),
            (".content", ".content"),
        ],
        "notes": [
            "httpx has a similar API to requests",
            "httpx also supports async with httpx.AsyncClient",
        ],
    },
    "simplejson": {
        "new": "json",
        "import_map": {
            "import simplejson": "import json",
        },
        "replacements": [
            ("import simplejson", "import json"),
            ("simplejson.dump(", "json.dump("),
            ("simplejson.dumps(", "json.dumps("),
            ("simplejson.load(", "json.load("),
            ("simplejson.loads(", "json.loads("),
        ],
        "notes": [
            "Python's built-in json module is sufficient for most use cases",
            "simplejson is only needed for specific edge cases with C extensions",
        ],
    },
    "chardet": {
        "new": "charset-normalizer",
        "import_map": {
            "import chardet": "import charset_normalizer",
        },
        "replacements": [
            ("import chardet", "import charset_normalizer"),
            ("chardet.detect(", "charset_normalizer.detect("),
        ],
        "notes": [
            "charset-normalizer is faster and used by requests internally",
            "chardet is largely deprecated in favor of charset-normalizer",
        ],
    },
}


def get_migration_guide(old_package: str, new_package: str) -> MigrationGuide:
    """Get migration guide for replacing a package."""
    guide = MigrationGuide(old_package=old_package, new_package=new_package)

    old_lower = old_package.lower().replace("-", "_")

    if old_lower in MIGRATION_GUIDES:
        migration = MIGRATION_GUIDES[old_lower]
        guide.general_notes = migration.get("notes", [])

        if "example_old" in migration:
            guide.general_notes.append(
                f"\nExample migration:\nOld: {migration['example_old']}\nNew: {migration['example_new']}"
            )

    return guide


def get_replacement_patterns(package_name: str) -> list[ReplacementPattern]:
    """Get replacement patterns for a package, sorted by length (longest first)."""
    old_lower = package_name.lower().replace("-", "_")

    if old_lower not in MIGRATION_GUIDES:
        return []

    migration = MIGRATION_GUIDES[old_lower]
    patterns = []

    all_replacements = []
    for old, new, *rest in migration.get("replacements", []):
        note = rest[0] if rest else ""
        all_replacements.append((old, new, note))

    for old, new in migration.get("import_map", {}).items():
        all_replacements.append((old, new, "Import statement"))

    all_replacements.sort(key=lambda x: len(x[0]), reverse=True)

    for old, new, note in all_replacements:
        patterns.append(ReplacementPattern(old=old, new=new, note=note))

    return patterns


def scan_for_usages(project_path: str, package_name: str) -> list[MigrationHint]:
    """Scan project for files that use a specific package."""
    hints = []
    patterns = get_replacement_patterns(package_name)

    if not patterns:
        patterns = _get_default_patterns(package_name)

    for root, _, files in os.walk(project_path):
        if any(skip in root for skip in ["venv", "__pycache__", ".git", "node_modules"]):
            continue

        for file in files:
            if not file.endswith(".py"):
                continue

            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        for pattern in patterns:
                            if pattern.old in line:
                                hints.append(MigrationHint(
                                    old_pattern=pattern.old,
                                    new_pattern=pattern.new,
                                    file_path=file_path,
                                    line_number=line_num,
                                    line_content=line.strip(),
                                    note=pattern.note,
                                ))
            except (UnicodeDecodeError, OSError):
                continue

    return hints


def _get_default_patterns(package_name: str) -> list[ReplacementPattern]:
    """Get default import patterns for unknown packages."""
    safe_name = package_name.lower().replace("-", "_")
    return [
        ReplacementPattern(old=f"import {safe_name}", new=f"import {safe_name}"),
        ReplacementPattern(old=f"from {safe_name} import", new=f"from {safe_name} import"),
    ]


def auto_replace_usages(project_path: str, old_package: str, new_package: str) -> tuple[int, list[str]]:
    """Automatically replace package usages in all Python files.

    Args:
        project_path: Path to the project.
        old_package: The old package name.
        new_package: The new package name.

    Returns:
        A tuple of (number of files modified, list of modified file paths).
    """
    hints = scan_for_usages(project_path, old_package)
    modified_files = []
    files_by_path: dict[str, list[MigrationHint]] = {}

    for hint in hints:
        if hint.file_path not in files_by_path:
            files_by_path[hint.file_path] = []
        files_by_path[hint.file_path].append(hint)

    for file_path, file_hints in files_by_path.items():
        try:
            shutil.copy2(file_path, f"{file_path}.bak")

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content
            changes_made = []

            for hint in file_hints:
                if hint.old_pattern in content:
                    content = content.replace(hint.old_pattern, hint.new_pattern)
                    changes_made.append(f"{hint.old_pattern} → {hint.new_pattern}")

            if content != original_content:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                modified_files.append(file_path)
                logger.info(f"Updated {len(changes_made)} patterns in {file_path}")

        except (OSError, IOError) as e:
            logger.error(f"Could not update {file_path}: {e}")

    return len(modified_files), modified_files


def generate_migration_summary(old_package: str, new_package: str, project_path: str) -> str:
    """Generate a human-readable migration summary."""
    guide = get_migration_guide(old_package, new_package)
    hints = scan_for_usages(project_path, old_package)

    lines = []
    lines.append(f"Migration Guide: {old_package} → {new_package}")
    lines.append("=" * 50)

    if guide.general_notes:
        lines.append("\nGeneral Notes:")
        for note in guide.general_notes:
            lines.append(f"  • {note}")

    if hints:
        files_seen = set()
        usage_count = len(hints)
        lines.append(f"\nCode patterns to update ({usage_count} occurrences):")
        for hint in hints:
            if hint.file_path not in files_seen:
                files_seen.add(hint.file_path)
                lines.append(f"\n  {hint.file_path}:")
            lines.append(f"    Line {hint.line_number}: Replace '{hint.old_pattern}' → '{hint.new_pattern}'")
            if hint.note:
                lines.append(f"      Note: {hint.note}")
    else:
        lines.append("\nNo direct usages of this package found in your code.")

    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    import sys
    if len(sys.argv) >= 3:
        project = sys.argv[1]
        old_pkg = sys.argv[2]
        new_pkg = sys.argv[3] if len(sys.argv) > 3 else old_pkg
        print(generate_migration_summary(old_pkg, new_pkg, project))
    else:
        print("Usage: python -m src.core.migration_guide <project_path> <old_package> [new_package]")
