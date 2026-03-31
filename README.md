# LibFix

A powerful Python dependency analyzer and updater that finds inactive dependencies, suggests alternatives, automatically migrates code, and audits dependency usage.

## Features

- **Dependency Detection**: Scans for `requirements.txt`, `setup.py`, `setup.cfg`, `pyproject.toml`, and `Pipfile`
- **Inactivity Analysis**: Identifies packages that haven't been updated in over 2 years
- **Alternative Suggestions**: Recommends actively maintained replacements
- **Automatic Migration**: Updates both dependency files AND source code imports/function calls
- **Usage Auditing**: Finds unused dependencies and missing imports
- **PyPI Integration**: Fetches latest versions and package information
- **Caching**: Local cache to speed up repeated analysis
- **CLI + GUI**: Use via command line or graphical interface

## Installation

```bash
# CLI only (no GUI)
pip install libfix

# Full installation with GUI
pip install libfix[gui]
```

Or for development:
```bash
git clone <repo-url>
cd LibFix
pip install -e ".[gui]"
```

## Usage

### GUI

```bash
python -m src.main
```

The GUI provides:
- **Select Python Project**: Choose a project to analyze
- **Audit Usage**: Check if dependencies are actually used in the code
- **Replace Selected**: Replace an inactive dependency with an alternative

### CLI

```bash
# Analyze a project
libfix analyze /path/to/project

# Show all packages (not just inactive)
libfix analyze . --show-all

# Output as JSON
libfix analyze . --output json

# Compact output
libfix analyze . --output compact

# Custom inactivity threshold (years)
libfix analyze . --threshold 3.0

# Manage cache
libfix cache clear
libfix cache info
```

## Workflow

1. **Select a project** - Choose a Python project directory
2. **Scan dependencies** - LibFix finds all dependency files
3. **Analyze packages** - Fetches PyPI data to check for inactivity
4. **Review results** - See inactive packages with alternative suggestions
5. **Replace dependency** - Choose an alternative to update requirements
6. **Auto-migrate code** - LibFix updates imports and function calls
7. **Audit usage** - Verify all dependencies are actually used in the code

## Dependency Usage Audit

LibFix can audit your project to find:

- **Unused dependencies**: Packages in requirements that aren't imported anywhere
- **Missing dependencies**: Imports that don't have corresponding entries in requirements

This helps:
- Remove bloat from `requirements.txt`
- Find packages you forgot to add to dependencies
- Verify migrations are complete

## Supported Migrations

LibFix can automatically migrate code for these packages:

| Old Package | New Package | What Gets Updated |
|------------|-------------|-------------------|
| `toml` | `tomllib` | Imports, `open()` file mode, `toml.load()` |
| `pytz` | `zoneinfo` | Imports, `timezone()`, `utc` references |
| `python-dateutil` | `pendulum` | Imports, `parser.parse()`, `relativedelta` |
| `seaborn` | `plotly` | Imports, `lineplot()`, `scatterplot()`, etc. |
| `mock` | `unittest.mock` | Imports, `Mock()` → `MagicMock()` |
| `ujson` | `orjson` | Imports, `dumps()`, `loads()` |
| `requests` | `httpx` | Imports, `get()`, `post()`, etc. |
| `simplejson` | `json` | Imports, `dump()`, `dumps()`, etc. |
| `chardet` | `charset-normalizer` | Imports, `detect()` |

## Configuration

### Custom Alternatives

Add your own package replacements programmatically:

```python
from src.core.alternatives import add_replacement
add_replacement("old-package", ["new-package-1", "new-package-2"])
```

### Extending Migration Guides

Edit `src/core/migration_guide.py` to add new migration patterns:

```python
"my-package": {
    "new": "my-new-package",
    "import_map": {
        "import my_package": "import my_new_package",
    },
    "replacements": [
        ("my_package.func(", "my_new_package.func("),
    ],
    "notes": [
        "Migration notes here",
    ],
}
```

## Project Structure

```
LibFix/
├── src/
│   ├── main.py              # GUI application
│   ├── cli.py               # Command-line interface
│   └── core/
│       ├── dependency_finder.py    # Find dependency files
│       ├── dependency_parser.py     # Parse various formats
│       ├── dependency_analyzer.py  # Check for inactivity
│       ├── dependency_replacer.py  # Update requirements files
│       ├── dependency_auditor.py  # Audit dependency usage
│       ├── pypi_utils.py           # PyPI API integration
│       ├── cache.py                # Local caching
│       ├── alternatives.py         # Alternative package suggestions
│       ├── migration_guide.py      # Code migration patterns
│       └── libraries_io.py        # Libraries.io integration
├── tests/                  # Unit tests (56 tests)
└── pyproject.toml          # Project configuration
```

## Requirements

- Python 3.10+
- PyQt6 (for GUI)
- requests
- toml
- python-dateutil
- packaging

## License

MIT
