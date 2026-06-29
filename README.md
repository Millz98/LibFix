# LibFix

A Python dependency analyzer that **learns** about your packages. Finds inactive dependencies, suggests alternatives, audits usage, migrates code, and gets smarter with every project you scan.

## What Makes LibFix Different

**LibFix learns.** Instead of relying solely on hardcoded lists, it:
- Fetches rich metadata from PyPI (classifiers, keywords, dependencies)
- Derives category, ecosystem, and alternatives for any package
- Remembers what it learns across sessions (`~/.libfix/knowledge/`)
- Tracks which packages appear together across your projects
- Adapts to new packages without code changes

## Features

- **Smart Inactivity Detection**: Uses PyPI release dates + classifiers + maintenance status
- **Dynamic Knowledge System**: Learns about ANY package — category, ecosystem, alternatives
- **Local Module Detection**: Recognizes your own modules (won't flag them as missing)
- **Auto-Acknowledge**: Remembers what you've already reviewed — only shows NEW issues
- **Usage Auditing**: Finds unused deps and missing imports with confidence scoring
- **Automatic Migration**: Updates requirements AND source code imports
- **Full Integration**: Installs packages via pip + adds imports + updates requirements
- **Persistent History**: Tracks resolved/acknowledged issues across re-scans
- **Deduplication**: Same package across multiple files shows once
- **Comprehensive Stdlib Detection**: Uses Python's own stdlib list (no false positives)
- **CLI + GUI**: Command line or graphical interface
- **Caching**: Local cache to speed up repeated analysis

## Installation

```bash
pip install libfix
```

Or for development:
```bash
git clone https://github.com/Millz98/LibFix.git
cd LibFix
pip install -e ".[gui]"
```

## Quick Start

### GUI
```bash
libfix
# or explicitly:
libfix gui
```

### CLI
```bash
# Analyze for inactive dependencies
libfix analyze /path/to/project

# Audit usage (unused/missing deps)
libfix audit /path/to/project

# Audit with JSON output
libfix audit . --output json

# Show all packages, not just inactive
libfix analyze . --show-all

# Custom inactivity threshold
libfix analyze . --threshold 3.0

# Cache management
libfix cache clear
libfix cache info
```

## How It Works

### 1. Dependency Analysis (Inactive Detection)
```
libfix analyze ~/my-project
```
- Scans requirements.txt, setup.py, pyproject.toml, Pipfile
- Fetches PyPI metadata for each package
- Flags packages not updated in 2+ years (configurable)
- Suggests alternatives from learned knowledge
- **Auto-acknowledges** after first scan — re-scans only show NEW issues

### 2. Usage Audit
```
libfix audit ~/my-project
```
- Finds **unused** dependencies (in requirements but not imported)
- Finds **missing** dependencies (imported but not in requirements)
- Identifies **local modules** (your own .py files/packages)
- Confidence scoring: HIGH (safe to remove), MEDIUM, LOW
- Filters out stdlib modules automatically (contextlib, asyncio, etc.)

### 3. Knowledge Learning
Every scan teaches LibFix:
- **Category**: web, database, testing, cli, data-science, etc.
- **Ecosystem**: django, flask, fastapi, ml, etc.
- **Alternatives**: 100+ known patterns + dynamic discovery
- **Co-occurrence**: which packages appear together

Knowledge persists in `~/.libfix/knowledge/` — the more you scan, the smarter it gets.

## GUI Features

- **Table view** with columns: Package, Required, Latest, Status
- **Details panel** showing category, ecosystem, summary, alternatives
- **Inactive deps sorted to top** with color-coded status
- **Right-click context menu**: copy name, acknowledge warning
- **Colored action buttons**: Select Project, Audit, Replace
- **Status bar** with project info and scan summary

## Audit History

LibFix tracks state in `.libfix/audit-history.json` (per-project):
- **Resolved**: Issues you fixed (replaced, removed, added)
- **Acknowledged**: Issues you chose to ignore
- **Auto-acknowledged**: Inactive deps automatically remembered after first scan

On re-scan, previously-handled issues are filtered out. Stale acknowledgments are cleaned up if a dep changes (e.g., gets a new release).

## Knowledge Storage

| Location | Purpose |
|----------|---------|
| `~/.libfix/knowledge/package-knowledge.json` | Learned package metadata |
| `~/.libfix/knowledge/cooccurrence.json` | Package relationship patterns |
| `~/.libfix/cache/` | PyPI API response cache |
| `.libfix/audit-history.json` | Per-project audit history |

## Confidence Scoring

| Level | Meaning | Auto-remove |
|-------|---------|-------------|
| **HIGH** | Static imports only, no dynamic usage | Yes |
| **MEDIUM** | Used in tests, examples, or setup files | No |
| **LOW** | Potentially used dynamically (importlib, plugins) | No |

## Supported Package Formats

- `requirements.txt`
- `setup.py` / `setup.cfg`
- `pyproject.toml`
- `Pipfile`

## Requirements

- Python 3.10+
- PyQt6 (for GUI)
- requests
- python-dateutil
- packaging
- qdarkstyle (for dark theme)

## License

MIT
