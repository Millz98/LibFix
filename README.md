# LibFix

A powerful Python dependency analyzer and updater that finds inactive dependencies, suggests alternatives, automatically migrates code, audits dependency usage, and integrates new packages.

## Features

- **Dependency Detection**: Scans for `requirements.txt`, `setup.py`, `setup.cfg`, `pyproject.toml`, and `Pipfile`
- **Inactivity Analysis**: Identifies packages that haven't been updated in over 2 years
- **Alternative Suggestions**: Recommends actively maintained replacements with built-in database
- **Automatic Migration**: Updates both dependency files AND source code imports/function calls
- **Usage Auditing**: Finds unused dependencies and missing imports with confidence scoring
- **Smart Safety**: Only auto-removes dependencies it can verify are safe (high confidence)
- **Audit History**: Tracks resolved/acknowledged issues across re-audits
- **Full Integration**: Installs packages via pip AND adds import statements
- **PyPI Integration**: Fetches latest versions and package information
- **Caching**: Local cache to speed up repeated analysis
- **Dynamic Import Detection**: Recognizes `importlib.import_module()`, `__import__()`, and lazy imports
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
- **Remove Unused Dependencies**: Safely remove unused packages (high confidence only)
- **Add to Requirements**: Add missing packages to requirements.txt
- **Full Integration**: Install package via pip + add import statements + update requirements
- **Acknowledge...**: Mark issues as "will not fix" to skip them in future audits

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

### Dependency Replacement

1. **Select a project** - Choose a Python project directory
2. **Scan dependencies** - LibFix finds all dependency files
3. **Analyze packages** - Fetches PyPI data to check for inactivity
4. **Review results** - See inactive packages with alternative suggestions
5. **Replace dependency** - Choose an alternative to update requirements
6. **Auto-migrate code** - LibFix updates imports and function calls

### Dependency Auditing

1. **Run audit** - Click "Audit Usage" to scan for unused/missing dependencies
2. **Review findings** - See confidence levels (SAFE vs CAUTION)
3. **Remove unused** - LibFix only removes high-confidence unused dependencies
4. **Add missing** - Install and integrate missing packages
5. **Acknowledge** - Skip issues you don't want to fix (they won't appear in future audits)

## Dependency Usage Audit

LibFix audits your project to find:

- **Unused dependencies**: Packages in requirements that aren't imported anywhere
- **Missing dependencies**: Imports that don't have corresponding entries in requirements

### Confidence Scoring

LibFix assigns confidence levels to help prevent breaking your project:

| Level | Meaning | Auto-remove |
|-------|---------|-------------|
| **HIGH** | Static imports detected, no dynamic usage | ✅ Yes |
| **MEDIUM** | Used in tests, examples, or setup files | ❌ No |
| **LOW** | Potentially used dynamically (`importlib`, plugins) | ❌ No |

### Safety Features

- Ignores `venv`, `__pycache__`, `.git` directories
- Recognizes package aliases (sklearn→scikit-learn, cv2→opencv-python, etc.)
- Detects dynamic imports (`importlib.import_module()`, `__import__()`)
- Creates `.bak` backup files before modifying
- Filters out previously resolved/acknowledged issues

### Audit History

LibFix tracks actions in `.libfix/audit-history.json`:
- **Resolved**: Issues you fixed (e.g., removed unused dependency)
- **Acknowledged**: Issues you chose to ignore with optional reason

On re-audit, previously handled issues won't appear again.

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

## Full Integration

The "Full Integration" button performs:

1. **Install via pip** - Skips non-PyPI packages (local dependencies)
2. **Add import statements** - Inserts proper imports into source files
3. **Update requirements** - Adds to requirements.txt

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

### Custom Inactivity Threshold

Edit `src/core/dependency_analyzer.py`:

```python
INACTIVITY_THRESHOLD_DAYS = 730  # 2 years (default)
```

## Project Structure

```
LibFix/
├── src/
│   ├── main.py                    # GUI application
│   ├── cli.py                     # Command-line interface
│   └── core/
│       ├── dependency_finder.py      # Find dependency files
│       ├── dependency_parser.py       # Parse various formats
│       ├── dependency_analyzer.py     # Check for inactivity
│       ├── dependency_replacer.py     # Update requirements files
│       ├── dependency_auditor.py      # Audit dependency usage
│       ├── dependency_integrator.py   # Install + add imports
│       ├── audit_history.py           # Track resolved issues
│       ├── pypi_utils.py              # PyPI API integration
│       ├── cache.py                   # Local caching
│       ├── alternatives.py            # Alternative package suggestions
│       └── migration_guide.py         # Code migration patterns
├── tests/                           # Unit tests (70 tests)
├── pyproject.toml                  # Project configuration
└── README.md
```

## Requirements

- Python 3.10+
- PyQt6 (for GUI)
- requests
- python-dateutil
- packaging
- qdarkstyle (for dark theme)

## License

MIT
