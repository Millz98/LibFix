import logging
import os
from typing import TypedDict

logger = logging.getLogger(__name__)


class DependencyFiles(TypedDict):
    requirements: list[str]
    setup: list[str]
    setup_cfg: list[str]
    pyproject: list[str]
    pipfile: list[str]


def find_dependency_files(project_directory: str) -> DependencyFiles:
    """Searches the given project directory for dependency files.

    Finds: requirements.txt, setup.py, setup.cfg, pyproject.toml, Pipfile

    Args:
        project_directory: The path to the Python project directory.

    Returns:
        A dictionary with file types as keys and lists of file paths as values.
    """
    dependency_files: DependencyFiles = {
        'requirements': [],
        'setup': [],
        'setup_cfg': [],
        'pyproject': [],
        'pipfile': [],
    }

    if not os.path.isdir(project_directory):
        logger.warning(f"Directory does not exist: {project_directory}")
        return dependency_files

    for root, _, files in os.walk(project_directory):
        for file in files:
            if file == 'requirements.txt' or file.startswith('requirements') and file.endswith('.txt'):
                dependency_files['requirements'].append(os.path.join(root, file))
            elif file == 'setup.py':
                dependency_files['setup'].append(os.path.join(root, file))
            elif file == 'setup.cfg':
                dependency_files['setup_cfg'].append(os.path.join(root, file))
            elif file == 'pyproject.toml':
                dependency_files['pyproject'].append(os.path.join(root, file))
            elif file == 'Pipfile':
                dependency_files['pipfile'].append(os.path.join(root, file))

    total = sum(len(files) for files in dependency_files.values())
    logger.debug(f"Found {total} dependency files: {dependency_files}")
    return dependency_files


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    import sys
    test_project = sys.argv[1] if len(sys.argv) > 1 else '.'
    found_files = find_dependency_files(test_project)
    print("Found dependency files:")
    for file_type, files in found_files.items():
        for file_path in files:
            print(f"  - {file_type}: {file_path}")
