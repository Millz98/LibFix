import logging
import os
import re
from typing import Optional

import toml

logger = logging.getLogger(__name__)


def parse_requirements_txt(file_path: str) -> list[str]:
    """Parses a requirements.txt file and returns a list of dependencies.

    Args:
        file_path: The path to the requirements.txt file.

    Returns:
        A list of dependency strings.
    """
    dependencies: list[str] = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('-'):
                    dependencies.append(line)
        logger.debug(f"Parsed {len(dependencies)} dependencies from {file_path}")
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
    except IOError as e:
        logger.error(f"Error reading {file_path}: {e}")
    return dependencies


def parse_setup_py(file_path: str) -> list[str]:
    """Parses a setup.py file and returns a list of dependencies.

    Handles both simple and multiline install_requires definitions.

    Args:
        file_path: The path to the setup.py file.

    Returns:
        A list of dependency strings.
    """
    dependencies: list[str] = []
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        match = re.search(r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if match:
            deps_str = match.group(1)
            deps_str = re.sub(r'["\']', '', deps_str)
            deps_str = re.sub(r'\\\s*', ' ', deps_str)

            for dep in deps_str.split(','):
                dep = dep.strip()
                dep = re.sub(r'\s+', '', dep)
                if dep:
                    dependencies.append(dep)
        logger.debug(f"Parsed {len(dependencies)} dependencies from {file_path}")
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
    except IOError as e:
        logger.error(f"Error reading {file_path}: {e}")
    return dependencies


def parse_setup_cfg(file_path: str) -> list[str]:
    """Parses a setup.cfg file and returns a list of dependencies.

    Supports both options.install_requires and options.packages.find.

    Args:
        file_path: The path to the setup.cfg file.

    Returns:
        A list of dependency strings.
    """
    dependencies: list[str] = []
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        dep_match = re.search(r'\[options\]\s*install_requires\s*=\s*(.*?)(?:\n\[|\Z)', content, re.DOTALL)
        if dep_match:
            deps_str = dep_match.group(1)
            for line in deps_str.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    dependencies.append(line)
        logger.debug(f"Parsed {len(dependencies)} dependencies from {file_path}")
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
    except IOError as e:
        logger.error(f"Error reading {file_path}: {e}")
    return dependencies


def parse_pyproject_toml(file_path: str) -> list[str]:
    """Parses a pyproject.toml file and returns dependencies.

    Supports Poetry, PIP, and modern PEP 621 formats.

    Args:
        file_path: The path to the pyproject.toml file.

    Returns:
        A list of dependency strings.
    """
    dependencies: list[str] = []
    try:
        with open(file_path, 'r') as f:
            data = toml.load(f)

        if 'project' in data and 'dependencies' in data['project']:
            deps = data['project']['dependencies']
            if isinstance(deps, dict):
                for package, version in deps.items():
                    dependencies.append(f"{package}{version if version != '*' else ''}")
            elif isinstance(deps, list):
                dependencies.extend(deps)

        if 'tool' in data:
            if 'poetry' in data['tool'] and 'dependencies' in data['tool']['poetry']:
                for package, version in data['tool']['poetry']['dependencies'].items():
                    if package != 'python':
                        dependencies.append(f"{package}{version if version != '*' else ''}")

            if 'pip-tools' in data['tool'] or 'pipenv' in data.get('packages', {}).get('dev', {}):
                pass

        logger.debug(f"Parsed {len(dependencies)} dependencies from {file_path}")
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
    except toml.TomlDecodeError as e:
        logger.error(f"Error decoding TOML in {file_path}: {e}")
    except IOError as e:
        logger.error(f"Error reading {file_path}: {e}")
    return dependencies


def parse_pipfile(file_path: str) -> list[str]:
    """Parses a Pipfile and returns a list of dependencies.

    Args:
        file_path: The path to the Pipfile.

    Returns:
        A list of dependency strings.
    """
    dependencies: list[str] = []
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        in_packages = False
        for line in content.split('\n'):
            line = line.strip()
            if line == '[packages]':
                in_packages = True
                continue
            elif line.startswith('['):
                in_packages = False
                continue

            if in_packages and line and not line.startswith('#'):
                if '=' in line:
                    parts = line.split('=', 1)
                    package = parts[0].strip()
                    version = parts[1].strip().strip('"').strip("'")
                    if version and version != '*':
                        dependencies.append(f"{package}{version}")
                    else:
                        dependencies.append(package)
        logger.debug(f"Parsed {len(dependencies)} dependencies from {file_path}")
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
    except IOError as e:
        logger.error(f"Error reading {file_path}: {e}")
    return dependencies


def parse_all(file_path: str) -> list[str]:
    """Auto-detect and parse any dependency file.

    Args:
        file_path: The path to the dependency file.

    Returns:
        A list of dependency strings, or empty list if format not recognized.
    """
    basename = os.path.basename(file_path)

    parsers = {
        'requirements.txt': parse_requirements_txt,
        'requirements-dev.txt': parse_requirements_txt,
        'requirements-test.txt': parse_requirements_txt,
        'setup.py': parse_setup_py,
        'setup.cfg': parse_setup_cfg,
        'pyproject.toml': parse_pyproject_toml,
        'Pipfile': parse_pipfile,
    }

    parser = parsers.get(basename)
    if parser:
        return parser(file_path)

    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.txt':
        return parse_requirements_txt(file_path)
    elif ext == '.cfg':
        return parse_setup_cfg(file_path)
    elif ext == '.toml':
        return parse_pyproject_toml(file_path)

    return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    import sys
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
        from .dependency_finder import find_dependency_files
        found_files = find_dependency_files(project_dir)
        all_deps = set()
        for file_type, files in found_files.items():
            for file_path in files:
                deps = parse_all(file_path)
                all_deps.update(deps)
        print(f"Found {len(all_deps)} unique dependencies:")
        for dep in sorted(all_deps):
            print(f"  - {dep}")
