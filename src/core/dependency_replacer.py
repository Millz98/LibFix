import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ReplacementResult:
    success: bool
    message: str
    file_path: Optional[str] = None
    original_dep: Optional[str] = None
    new_dep: Optional[str] = None


def replace_dependency(
    project_path: str,
    old_dep: str,
    new_dep: str,
    create_backup: bool = True
) -> ReplacementResult:
    """Replace a dependency in project files.

    Args:
        project_path: Path to the project directory.
        old_dep: The old dependency to replace (e.g., "toml>=0.10.2").
        new_dep: The new dependency to use (e.g., "tomllib>=1.0").
        create_backup: Whether to create backup files.

    Returns:
        A ReplacementResult indicating success or failure.
    """
    package_name = _extract_package_name(old_dep)
    old_pattern = _create_dependency_pattern(package_name)

    files_modified = []

    for root, _, files in os.walk(project_path):
        for file in files:
            if file in ['requirements.txt', 'setup.py', 'setup.cfg', 'pyproject.toml']:
                file_path = os.path.join(root, file)
                try:
                    result = _replace_in_file(file_path, old_pattern, old_dep, new_dep, create_backup)
                    if result:
                        files_modified.append(file_path)
                except Exception as e:
                    logger.error(f"Error modifying {file_path}: {e}")

    if files_modified:
        logger.info(f"Replaced '{old_dep}' with '{new_dep}' in {len(files_modified)} files")
        return ReplacementResult(
            success=True,
            message=f"Replaced '{old_dep}' with '{new_dep}' in {len(files_modified)} file(s)",
            file_path=', '.join(files_modified),
            original_dep=old_dep,
            new_dep=new_dep
        )
    else:
        return ReplacementResult(
            success=False,
            message=f"Could not find '{old_dep}' in any dependency file"
        )


def _replace_in_file(
    file_path: str,
    old_pattern: str,
    old_dep: str,
    new_dep: str,
    create_backup: bool
) -> bool:
    """Replace dependency in a single file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content

    if file_path.endswith('.py'):
        new_content = _replace_in_python(content, old_pattern, old_dep, new_dep)
    elif file_path.endswith('.toml'):
        new_content = _replace_in_toml(content, old_dep, new_dep)
    elif file_path.endswith('.txt') or file_path.endswith('.cfg'):
        new_content = _replace_in_text(content, old_dep, new_dep)

    if new_content != content:
        if create_backup:
            backup_path = f"{file_path}.bak"
            shutil.copy2(file_path, backup_path)
            logger.debug(f"Created backup: {backup_path}")

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        logger.info(f"Modified: {file_path}")
        return True

    return False


def _replace_in_python(content: str, old_pattern: str, old_dep: str, new_dep: str) -> str:
    """Replace in setup.py style files."""
    new_dep_name = _extract_package_name(new_dep)
    new_content = re.sub(old_pattern, f"'{new_dep}'", content)
    new_content = re.sub(rf"(?i){re.escape(new_dep_name)}", lambda m: m.group(0), new_content)
    return new_content


def _replace_in_toml(content: str, old_dep: str, new_dep: str) -> str:
    """Replace in pyproject.toml or Pipfile."""
    old_name = _extract_package_name(old_dep)
    new_name = _extract_package_name(new_dep)

    new_content = content
    new_content = re.sub(rf'["\']?{re.escape(old_name)}.*?["\']', f'"{new_dep}"', new_content)
    return new_content


def _replace_in_text(content: str, old_dep: str, new_dep: str) -> str:
    """Replace in requirements.txt or setup.cfg."""
    old_name = _extract_package_name(old_dep)
    new_content = re.sub(rf'^{re.escape(old_name)}.*$', new_dep, content, flags=re.MULTILINE)
    return new_content


def _extract_package_name(dependency_string: str) -> str:
    """Extract just the package name from a dependency string."""
    parts = dependency_string.split('>', 1)[0].split('<', 1)[0].split('=', 1)[0].split('!', 1)[0].split('[', 1)[0]
    return parts.strip()


def _create_dependency_pattern(package_name: str) -> str:
    """Create a regex pattern for matching the package."""
    return rf"['\"]({re.escape(package_name)}.*?)['\"]"


def restore_backup(file_path: str) -> bool:
    """Restore a file from its backup.

    Args:
        file_path: Path to the original file (backup should be at file_path.bak).

    Returns:
        True if restore was successful.
    """
    backup_path = f"{file_path}.bak"
    if os.path.exists(backup_path):
        shutil.move(backup_path, file_path)
        logger.info(f"Restored: {file_path}")
        return True
    return False


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) >= 4:
        project = sys.argv[1]
        old = sys.argv[2]
        new = sys.argv[3]
        result = replace_dependency(project, old, new)
        print(f"\nResult: {result.message}")
        if result.success:
            print(f"Files modified: {result.file_path}")
    else:
        print("Usage: python -m src.core.dependency_replacer <project_path> <old_dep> <new_dep>")
