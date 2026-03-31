import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class UsageResult:
    package_name: str
    is_used: bool
    import_lines: list[tuple[str, int]]
    is_optional: bool = False


@dataclass
class AuditResult:
    unused_dependencies: list[UsageResult]
    missing_dependencies: list[tuple[str, list[str]]]
    all_dependencies: list[UsageResult]
    summary: str


KNOWN_STANDARD_LIB = {
    "os", "sys", "re", "json", "time", "datetime", "date", "timedelta",
    "collections", "itertools", "functools", "operator", "enum", "typing",
    "pathlib", "urllib", "http", "html", "xml", "csv", "io", "buffer",
    "copy", "pickle", "shelve", "sqlite3", "logging", "warnings",
    "threading", "multiprocessing", "subprocess", "socket", "ssl",
    "email", "smtplib", "poplib", "imaplib", "uuid", "hashlib",
    "hmac", "secrets", "base64", "binascii", "struct", "codecs",
    "argparse", "optparse", "getopt", "configparser", "argparse",
    "platform", "sysconfig", "abc", "asyncio", "gc", "weakref",
    "types", "inspect", "dis", "compileall", "marshal", "code",
    "ast", "symtable", "tokenize", "keyword", "token", "linecache",
    "random", "statistics", "math", "cmath", "decimal", "fractions",
    "numbers", "curses", "textwrap", "string", "unicodedata", "locale",
    "gettext", "bundles", "gzip", "bz2", "lzma", "zipfile", "tarfile",
    "shutil", "glob", "fnmatch", "tempfile", "tempdir", "fileinput",
    "stat", "statvfs", "filecmp", "dirent", "msvcrt", "readline",
    "parser", "symbol", "ast", "fpectl", "pty", "tty", "fcntl",
    "pipes", "errno", "syslog", "resource", "nis", "grp", "pwd",
    "spwd", "crypt", "termios", "TERMIOS", "select", "poll", "kqueue",
    "mmap", "reprlib", "graphlib", "contextvars", "dataclasses",
    "heapq", "traceback", "unittest", "atexit", "gc", "trace",
    "functools", "itertools", "collections", "copy", "pprint",
    "textwrap", "unicodedata", "warnings", "signal", "inspect",
}

PACKAGE_ALIASES = {
    "sklearn": "scikit-learn",
    "PIL": "pillow",
    "pil": "pillow",
    "cv2": "opencv-python",
    "tensorflow": "tf",
}


def scan_imports(project_path: str) -> dict[str, list[tuple[str, int]]]:
    """Scan project for all imports.

    Returns:
        Dict mapping package names to list of (file_path, line_number).
    """
    imports: dict[str, list[tuple[str, int]]] = {}

    for root, _, files in os.walk(project_path):
        if any(skip in root for skip in ["venv", "__pycache__", ".git", ".venv", "node_modules"]):
            continue

        for file in files:
            if not file.endswith(".py"):
                continue

            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue

                        import_matches = _extract_imports(line)
                        for imp in import_matches:
                            pkg_name = _normalize_package_name(imp)
                            if pkg_name and pkg_name not in KNOWN_STANDARD_LIB:
                                if pkg_name not in imports:
                                    imports[pkg_name] = []
                                imports[pkg_name].append((file_path, line_num))
            except (OSError, UnicodeDecodeError):
                continue

    return imports


def _extract_imports(line: str) -> list[str]:
    """Extract import names from a line of code."""
    imports = []

    if line.startswith("import "):
        parts = line[7:].split(",")
        for part in parts:
            name = part.strip().split(" as ")[0].strip().split(".")[0]
            if name:
                imports.append(name)

    elif line.startswith("from "):
        match = re.match(r"from\s+([\w.]+)\s+import", line)
        if match:
            name = match.group(1).split(".")[0]
            if name:
                imports.append(name)

    return imports


def _normalize_package_name(name: str) -> str:
    """Normalize package name for comparison."""
    name = name.lower().replace("-", "_")
    return name


def audit_dependencies(
    project_path: str,
    dependencies: list[str],
    known_optional: Optional[list[str]] = None,
    project_name: Optional[str] = None
) -> AuditResult:
    """Audit dependencies against actual usage in the project.

    Args:
        project_path: Path to the project.
        dependencies: List of dependency strings (e.g., "requests>=2.28").
        known_optional: List of optional dependency names.
        project_name: Name of the project (to exclude from missing deps).

    Returns:
        AuditResult with unused, missing, and all dependencies.
    """
    known_optional = known_optional or []
    imports = scan_imports(project_path)

    dep_results: list[UsageResult] = []
    unused: list[UsageResult] = []
    missing: list[tuple[str, list[str]]] = []

    dep_names_normalized = {_normalize_package_name(_extract_package_name(d)) for d in dependencies}
    for alias, real in PACKAGE_ALIASES.items():
        if _normalize_package_name(real) in dep_names_normalized:
            dep_names_normalized.add(_normalize_package_name(alias))

    if project_name:
        dep_names_normalized.add(_normalize_package_name(project_name))

    for dep in dependencies:
        pkg_name = _extract_package_name(dep)
        pkg_normalized = _normalize_package_name(pkg_name)

        import_lines = []

        for imp_name, lines in imports.items():
            imp_normalized = _normalize_package_name(imp_name)
            if imp_normalized == pkg_normalized:
                import_lines.extend(lines)
            if imp_normalized in PACKAGE_ALIASES:
                alias_target = _normalize_package_name(PACKAGE_ALIASES[imp_normalized])
                if alias_target == pkg_normalized:
                    import_lines.extend(lines)

        is_used = len(import_lines) > 0
        is_optional = pkg_normalized in {_normalize_package_name(o) for o in known_optional}

        result = UsageResult(
            package_name=pkg_name,
            is_used=is_used,
            import_lines=import_lines,
            is_optional=is_optional,
        )
        dep_results.append(result)

        if not is_used and not is_optional:
            unused.append(result)

    for imp_name, lines in imports.items():
        imp_normalized = _normalize_package_name(imp_name)

        if imp_normalized in KNOWN_STANDARD_LIB:
            continue

        if imp_normalized in dep_names_normalized:
            continue

        if imp_normalized in PACKAGE_ALIASES:
            alias_target = _normalize_package_name(PACKAGE_ALIASES[imp_normalized])
            if alias_target in dep_names_normalized:
                continue

        files = [line[0] for line in lines]
        missing.append((imp_name, files))

    unused_summary = f"{len(unused)} unused" if unused else "All dependencies used"
    missing_summary = f"{len(missing)} missing" if missing else "No missing dependencies"

    summary = f"Audit complete: {unused_summary}, {missing_summary}"

    return AuditResult(
        unused_dependencies=unused,
        missing_dependencies=missing,
        all_dependencies=dep_results,
        summary=summary,
    )


def _extract_package_name(dependency_string: str) -> str:
    """Extract package name from dependency string."""
    name = dependency_string.split(">")[0].split("<")[0].split("=")[0].split("!")[0].split("[")[0].split(";")[0]
    return name.strip()


def generate_audit_report(result: AuditResult) -> str:
    """Generate a human-readable audit report."""
    lines = []
    lines.append("=" * 50)
    lines.append("DEPENDENCY USAGE AUDIT REPORT")
    lines.append("=" * 50)

    if result.unused_dependencies:
        lines.append(f"\n⚠️  UNUSED DEPENDENCIES ({len(result.unused_dependencies)}):")
        for dep in result.unused_dependencies:
            if not dep.is_optional:
                lines.append(f"  • {dep.package_name}")

    if result.missing_dependencies:
        lines.append(f"\n⚠️  MISSING DEPENDENCIES ({len(result.missing_dependencies)}):")
        for pkg, files in result.missing_dependencies:
            lines.append(f"  • {pkg}")
            for f in files[:3]:
                lines.append(f"      - {f}")
            if len(files) > 3:
                lines.append(f"      ... and {len(files) - 3} more")

    if not result.unused_dependencies and not result.missing_dependencies:
        lines.append("\n✅ All dependencies are used and no missing dependencies!")

    lines.append(f"\n{result.summary}")

    return "\n".join(lines)


def remove_unused_dependencies(
    project_path: str,
    unused_dependencies: list[str],
    create_backup: bool = True
) -> tuple[int, list[str]]:
    """Remove unused dependencies from project files.

    Args:
        project_path: Path to the project.
        unused_dependencies: List of package names to remove.
        create_backup: Whether to create backup files.

    Returns:
        Tuple of (files modified count, list of modified files).
    """
    import shutil
    from .dependency_parser import parse_all

    modified_files = []

    for root, _, files in os.walk(project_path):
        if any(skip in root for skip in ["venv", "__pycache__", ".git"]):
            continue

        for file in files:
            if file not in ["requirements.txt", "setup.py", "setup.cfg", "pyproject.toml"]:
                continue

            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                original = content

                for dep in unused_dependencies:
                    dep_normalized = _normalize_package_name(dep)

                    if file.endswith(".py"):
                        content = _remove_from_python(content, dep_normalized)
                    elif file.endswith(".txt"):
                        content = _remove_from_requirements(content, dep)
                    elif file.endswith(".cfg"):
                        content = _remove_from_setup_cfg(content, dep)
                    elif file.endswith(".toml"):
                        content = _remove_from_toml(content, dep)

                if content != original:
                    if create_backup:
                        shutil.copy2(file_path, f"{file_path}.bak")

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)

                    modified_files.append(file_path)
                    logger.info(f"Removed unused deps from {file_path}")

            except (OSError, UnicodeDecodeError) as e:
                logger.error(f"Error updating {file_path}: {e}")

    return len(modified_files), modified_files


def _remove_from_python(content: str, package_name: str) -> str:
    import re
    lines = content.split("\n")
    new_lines = []
    skip_next = False

    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        if re.search(rf"install_requires\s*=\s*\[", line):
            bracket_line = i
            bracket_count = 0
            dep_lines = []
            started = False

            for j in range(i, min(i + 20, len(lines))):
                dep_lines.append(lines[j])
                if "[" in lines[j]:
                    bracket_count += lines[j].count("[")
                if "]" in lines[j]:
                    bracket_count -= lines[j].count("]")
                if bracket_count <= 0 and started:
                    break
                started = True

            dep_block = "\n".join(dep_lines)
            for dep in [package_name, package_name.replace("_", "-")]:
                dep_block = re.sub(rf"['\"]?\b{re.escape(dep)}\b[^'\"]*['\"]?\s*,?\s*", "", dep_block)
                dep_block = re.sub(rf",\s*\n\s*['\"]?\b{re.escape(dep)}\b", "", dep_block)

            new_lines.extend(dep_block.split("\n"))
            i = j
        else:
            new_lines.append(line)

    return "\n".join(new_lines)


def _remove_from_requirements(content: str, package_name: str) -> str:
    import re
    lines = content.split("\n")
    new_lines = []

    for line in lines:
        if line.strip().startswith("#"):
            new_lines.append(line)
            continue

        dep_normalized = _normalize_package_name(package_name)
        line_name = _normalize_package_name(_extract_package_name(line))

        if line_name == dep_normalized or line_name == package_name.replace("_", "-"):
            continue

        new_lines.append(line)

    return "\n".join(new_lines)


def _remove_from_setup_cfg(content: str, package_name: str) -> str:
    import re
    dep_normalized = _normalize_package_name(package_name)

    content = re.sub(
        rf"^\s*{re.escape(package_name)}[^\n]*\n",
        "",
        content,
        flags=re.MULTILINE
    )

    return content


def _remove_from_toml(content: str, package_name: str) -> str:
    import re
    dep_normalized = _normalize_package_name(package_name)

    content = re.sub(
        rf'["\']?\b{re.escape(package_name)}\b[^"\']*["\']?\s*[,\]]',
        "",
        content
    )

    return content


def add_missing_dependencies(
    project_path: str,
    missing_dependencies: list[str]
) -> tuple[int, list[str]]:
    """Add missing dependencies to project files.

    Args:
        project_path: Path to the project.
        missing_dependencies: List of package names to add.

    Returns:
        Tuple of (files modified count, list of modified files).
    """
    req_files = []
    for root, _, files in os.walk(project_path):
        if any(skip in root for skip in ["venv", "__pycache__", ".git"]):
            continue
        for file in files:
            if file == "requirements.txt":
                req_files.append(os.path.join(root, file))

    if not req_files:
        logger.warning("No requirements.txt found")
        return 0, []

    modified_files = []
    for req_file in req_files:
        try:
            with open(req_file, "r", encoding="utf-8") as f:
                content = f.read()

            original = content

            for dep in missing_dependencies:
                dep_normalized = _normalize_package_name(dep)
                if dep_normalized not in content:
                    if not content.endswith("\n"):
                        content += "\n"
                    content += f"{dep}\n"
                    logger.info(f"Added {dep} to {req_file}")

            if content != original:
                with open(req_file, "w", encoding="utf-8") as f:
                    f.write(content)
                modified_files.append(req_file)

        except (OSError, UnicodeDecodeError) as e:
            logger.error(f"Error updating {req_file}: {e}")

    return len(modified_files), modified_files


if __name__ == "__main__":
    import sys
    import tempfile

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        project = sys.argv[1]
        deps = ["requests", "numpy", "pandas", "nonexistent-package"]
        result = audit_dependencies(project, deps)
        print(generate_audit_report(result))
    else:
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("import requests\nimport json\n")

        result = audit_dependencies(temp_dir, ["requests", "unused-pkg", "json"])
        print(generate_audit_report(result))

        os.unlink(test_file)
        os.rmdir(temp_dir)
