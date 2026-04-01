import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class IntegrationResult:
    success: bool
    package: str
    installed: bool = False
    imports_added: list[tuple[str, int]] = None
    errors: list[str] = None
    message: str = ""

    def __post_init__(self):
        if self.imports_added is None:
            self.imports_added = []
        if self.errors is None:
            self.errors = []


def install_package(package_name: str, upgrade: bool = False) -> tuple[bool, str]:
    """Install a package using pip.

    Args:
        package_name: Name of package to install.
        upgrade: Whether to upgrade if already installed.

    Returns:
        Tuple of (success, message).
    """
    try:
        cmd = [sys.executable, "-m", "pip", "install"]
        if upgrade:
            cmd.append("--upgrade")
        cmd.append(package_name)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            logger.info(f"Successfully installed {package_name}")
            return True, f"Installed {package_name}"
        else:
            error_msg = result.stderr or result.stdout
            logger.error(f"Failed to install {package_name}: {error_msg}")
            return False, f"Installation failed: {error_msg[:200]}"

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout installing {package_name}")
        return False, "Installation timed out"
    except Exception as e:
        logger.error(f"Error installing {package_name}: {e}")
        return False, f"Error: {str(e)[:200]}"


def get_import_statement(package_name: str) -> str:
    """Generate the import statement for a package.

    Args:
        package_name: Name of the package.

    Returns:
        The import statement.
    """
    normalized = package_name.lower().replace("-", "_")

    common_imports = {
        "numpy": "import numpy as np",
        "pandas": "import pandas as pd",
        "matplotlib": "import matplotlib.pyplot as plt",
        "sklearn": "from sklearn import datasets",
        "scikit_learn": "from sklearn import datasets",
        "requests": "import requests",
        "flask": "import flask",
        "django": "import django",
        "fastapi": "import fastapi",
        "pytorch": "import torch",
        "tensorflow": "import tensorflow as tf",
        "keras": "import keras",
        "seaborn": "import seaborn as sns",
        "plotly": "import plotly.express as px",
        "scipy": "import scipy",
        "pillow": "from PIL import Image",
        "opencv": "import cv2",
        "opencv_python": "import cv2",
        "numpy": "import numpy as np",
        "pandas": "import pandas as pd",
    }

    if normalized in common_imports:
        return common_imports[normalized]

    if "_" in package_name:
        parts = package_name.replace("-", "_").split("_")
        return f"import {'.'.join(parts)}"

    return f"import {package_name}"


def add_import_to_file(file_path: str, package_name: str) -> tuple[bool, str]:
    """Add import statement to a Python file.

    Args:
        file_path: Path to the Python file.
        package_name: Name of package to import.

    Returns:
        Tuple of (success, message).
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        import_stmt = get_import_statement(package_name)
        normalized = package_name.lower().replace("-", "_")

        if normalized in content or import_stmt in content:
            return True, f"Import already exists in {file_path}"

        if "import " in content:
            lines = content.split("\n")
            import_lines = []
            other_lines = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    import_lines.append(line)
                else:
                    other_lines.append(line)

            import_lines.sort()
            new_content = "\n".join(import_lines) + "\n\n" + "\n".join(other_lines)
        else:
            new_content = f"import {package_name}\n\n" + content

        shutil.copy2(file_path, f"{file_path}.bak")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        logger.info(f"Added import to {file_path}")
        return True, f"Added import to {file_path}"

    except Exception as e:
        logger.error(f"Error adding import to {file_path}: {e}")
        return False, f"Error: {str(e)}"


def add_imports_to_project(
    project_path: str,
    package_name: str,
    files_with_imports: list[str]
) -> tuple[int, list[tuple[str, bool, str]]]:
    """Add import statements to multiple files in a project.

    Args:
        project_path: Path to the project.
        package_name: Name of package to import.
        files_with_imports: List of files that use this package.

    Returns:
        Tuple of (count added, list of (file, success, message)).
    """
    results = []
    count = 0

    for file_path in files_with_imports:
        if not os.path.exists(file_path):
            results.append((file_path, False, "File not found"))
            continue

        if not file_path.endswith(".py"):
            continue

        success, msg = add_import_to_file(file_path, package_name)
        results.append((file_path, success, msg))
        if success:
            count += 1

    return count, results


def integrate_dependency(
    project_path: str,
    package_name: str,
    files_using_it: list[str],
    install: bool = True
) -> IntegrationResult:
    """Fully integrate a dependency into a project.

    Args:
        project_path: Path to the project.
        package_name: Name of the package.
        files_using_it: Files that import this package.
        install: Whether to install the package via pip.

    Returns:
        IntegrationResult with details of what was done.
    """
    result = IntegrationResult(success=False, package=package_name)
    messages = []

    if install:
        success, msg = install_package(package_name)
        result.installed = success
        messages.append(msg)
        if not success:
            result.errors.append(msg)

    if files_using_it:
        count, results = add_imports_to_project(project_path, package_name, files_using_it)
        result.imports_added = [(f, s) for f, s, _ in results]
        messages.append(f"Added imports to {count} file(s)")
    else:
        messages.append("No files found using this package")

    result.success = len(result.errors) == 0
    result.message = "; ".join(messages)

    return result


def integrate_missing_dependencies(
    project_path: str,
    missing_dependencies: list[tuple[str, list[str]]],
    install: bool = True
) -> list[IntegrationResult]:
    """Integrate all missing dependencies into a project.

    Args:
        project_path: Path to the project.
        missing_dependencies: List of (package, files) tuples.
        install: Whether to install packages via pip.

    Returns:
        List of IntegrationResults.
    """
    results = []

    for package, files in missing_dependencies:
        result = integrate_dependency(
            project_path,
            package,
            files,
            install=install
        )
        results.append(result)

    return results


if __name__ == "__main__":
    import tempfile

    logging.basicConfig(level=logging.INFO)

    temp_dir = tempfile.mkdtemp()
    test_file = os.path.join(temp_dir, "test.py")

    with open(test_file, "w") as f:
        f.write("print('hello')\n")

    result = integrate_dependency(temp_dir, "requests", [test_file], install=False)

    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print(f"Installed: {result.installed}")

    with open(test_file, "r") as f:
        print(f"File content:\n{f.read()}")

    os.unlink(test_file)
    os.unlink(f"{test_file}.bak")
    os.rmdir(temp_dir)
