import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class UsageResult:
    package_name: str
    is_used: bool
    import_lines: list[tuple[str, int]] = field(default_factory=list)
    is_optional: bool = False
    confidence: str = "high"
    usage_type: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    unused_dependencies: list[UsageResult]
    missing_dependencies: list[tuple[str, list[str]]]
    all_dependencies: list[UsageResult]
    summary: str
    resolved_count: int = 0
    acknowledged_count: int = 0
    is_re_audit: bool = False


KNOWN_STANDARD_LIB: set[str] = {
    "os", "sys", "re", "json", "time", "datetime", "date", "timedelta",
    "collections", "itertools", "functools", "operator", "enum", "typing",
    "pathlib", "urllib", "http", "html", "xml", "csv", "io", "buffer",
    "copy", "pickle", "shelve", "sqlite3", "logging", "warnings",
    "threading", "multiprocessing", "subprocess", "socket", "ssl",
    "email", "smtplib", "poplib", "imaplib", "uuid", "hashlib",
    "hmac", "secrets", "base64", "binascii", "struct", "codecs",
    "argparse", "optparse", "getopt", "configparser",
    "platform", "sysconfig", "abc", "asyncio", "gc", "weakref",
    "types", "inspect", "dis", "compileall", "marshal", "code",
    "ast", "symtable", "tokenize", "keyword", "token", "linecache",
    "random", "statistics", "math", "cmath", "decimal", "fractions",
    "numbers", "curses", "textwrap", "string", "unicodedata", "locale",
    "gettext", "gzip", "bz2", "lzma", "zipfile", "tarfile",
    "shutil", "glob", "fnmatch", "tempfile", "tempdir", "fileinput",
    "stat", "filecmp", "select", "poll", "mmap",
    "heapq", "traceback", "unittest", "atexit", "trace",
    "pprint", "signal", "contextvars", "dataclasses",
    "graphlib", "pkgutil", "zipimport", "imp", "importlib",
    "fractions", "bisect", "array", "copyreg", "dbm", "msvcrt",
    "grp", "pwd", "termios", "fcntl", "resource", "errno",
    "exceptions", "Builtins", "PrettyTable", "colorsys",
    "concurrent", "concurrent.futures", "multiprocessing.pool",
    "queue", "mimetypes", "netrc", "plistlib", "zipfile",
    "sched", "queue", "ensurepip", "venv", "zipapp",
    "pkg_resources", "setuptools", "distutils",
    "py_compile", "compile", "py_compile",
    "tkinter", "Tkinter", "tkinter",
    "turtle", "formatter", "antigravity",
    "cgi", "cgihost", " turtledemo",
}

PACKAGE_ALIASES: dict[str, str] = {
    "sklearn": "scikit-learn",
    "PIL": "pillow",
    "pil": "pillow",
    "cv2": "opencv-python",
    "cv": "opencv-python",
    "tensorflow": "tf",
    "tf": "tensorflow",
    "np": "numpy",
    "pd": "pandas",
    "plt": "matplotlib",
    "sns": "seaborn",
    "pd": "pandas",
    "torch": "pytorch",
    "keras": "keras",
    "sk": "scikit-learn",
    "sp": "scipy",
    "sc": "scipy",
    "bs4": "beautifulsoup4",
    "bs": "beautifulsoup4",
    "yaml": "pyyaml",
    "yml": "pyyaml",
    "ftfy": "ftfy",
    "uj": "ujson",
    "ujson": "ujson",
    "simplejson": "simplejson",
    "sqlalchemy": "sqlalchemy",
    "psycopg2": "psycopg2-binary",
    "pg2": "psycopg2-binary",
}

DYNAMIC_IMPORT_PATTERNS: list[tuple[str, str]] = [
    (r"importlib\.import_module\s*\(\s*['\"](\w+)['\"]", "importlib.import_module"),
    (r"importlib\.import_module\s*\(\s*f['\"].*?['\"]", "importlib.import_module (dynamic)"),
    (r"__import__\s*\(\s*['\"](\w+)['\"]", "__import__"),
    (r"__import__\s*\(\s*f['\"].*?['\"]", "__import__ (dynamic)"),
    (r"from\s+importlib\s+import\s+lazy_loader", "lazy import"),
    (r"importlib\.LazyLoader", "lazy import"),
    (r"getattr\s*\(\s*__import__\s*\(", "dynamic __import__"),
    (r"exec\s*\(\s*['\"]import\s+(\w+)", "exec import"),
    (r"eval\s*\(\s*['\"]import\s+(\w+)", "eval import"),
]

ENTRY_POINT_PATTERNS: list[tuple[str, str]] = [
    (r"entry_points\s*=", "entry points"),
    (r"console_scripts\s*=", "console scripts"),
    (r"gui_scripts\s*=", "gui scripts"),
    (r"scripts\s*=", "scripts"),
    (r"pkg_resources\.EntryPoint", "pkg_resources entry"),
]

PLUGIN_PATTERNS: list[tuple[str, str]] = [
    (r"pluggy\.register", "pluggy plugin"),
    (r"stevedore", "stevedore plugin"),
    (r"yaml\.add_constructor", "yaml plugin"),
    (r"\.register\s*\(", "plugin registration"),
    (r"setuptools\.find_packages", "setuptools discovery"),
    (r"pkg_resources\.iter_entry_points", "pkg_resources discovery"),
]


def scan_imports(project_path: str) -> dict[str, list[tuple[str, int]]]:
    """Scan project for all imports.

    Returns:
        Dict mapping package names to list of (file_path, line_number).
    """
    imports: dict[str, list[tuple[str, int]]] = {}
    dynamic_imports: dict[str, list[tuple[str, int]]] = {}

    for root, _, files in os.walk(project_path):
        if any(skip in root for skip in ["venv", "__pycache__", ".git", ".venv", "node_modules"]):
            continue

        for file in files:
            if not file.endswith(".py"):
                continue

            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                for line_num, line in enumerate(content.split("\n"), 1):
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

                for pattern, ptype in DYNAMIC_IMPORT_PATTERNS:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if match.lastindex and match.lastindex >= 1:
                            pkg_name = _normalize_package_name(match.group(1))
                        else:
                            pkg_name = "(dynamic)"
                        if pkg_name not in dynamic_imports:
                            dynamic_imports[pkg_name] = []
                        dynamic_imports[pkg_name].append((file_path, 0))

            except (OSError, UnicodeDecodeError):
                continue

    for pkg, lines in dynamic_imports.items():
        if pkg != "(dynamic)":
            if pkg not in imports:
                imports[pkg] = []
            imports[pkg].extend(lines)

    return imports


def check_file_for_patterns(file_path: str, patterns: list[tuple[str, str]]) -> bool:
    """Check if a file contains any of the given patterns."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for pattern, _ in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
    except (OSError, UnicodeDecodeError):
        pass
    return False


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
    name = name.lower().replace("-", "_").replace(".", "_")
    return name


def _check_dependency_safety(
    project_path: str,
    package_name: str,
    pkg_normalized: str
) -> tuple[str, list[str]]:
    """Check if a dependency is used in potentially dynamic ways.

    Returns:
        Tuple of (confidence_level, list of usage_types).
    """
    usage_types = []
    confidence = "high"

    for root, _, files in os.walk(project_path):
        if any(skip in root for skip in ["venv", "__pycache__", ".git", ".venv"]):
            continue

        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, project_path)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if pkg_normalized in content.lower():
                    if file.endswith(".py"):
                        for pattern, ptype in DYNAMIC_IMPORT_PATTERNS:
                            if re.search(pattern, content, re.IGNORECASE):
                                if ptype not in usage_types:
                                    usage_types.append(ptype)
                                confidence = "low"

                    for pattern, ptype in ENTRY_POINT_PATTERNS:
                        if re.search(pattern, content, re.IGNORECASE):
                            if ptype not in usage_types:
                                usage_types.append(ptype)

                    for pattern, ptype in PLUGIN_PATTERNS:
                        if re.search(pattern, content, re.IGNORECASE):
                            if ptype not in usage_types:
                                usage_types.append(ptype)

                    if "pytest" in rel_path or "test_" in file or "_test.py" in file:
                        if "test" not in usage_types:
                            usage_types.append("test usage")
                        confidence = "medium"

                    if "setup.py" in file or "pyproject.toml" in file:
                        if "setup" not in usage_types:
                            usage_types.append("setup/dependency")
                        confidence = "medium"

                    if any(x in rel_path for x in ["examples", "demo", "scripts"]):
                        if "example" not in usage_types:
                            usage_types.append("example/demo script")
                        confidence = "medium"

            except (OSError, UnicodeDecodeError):
                continue

    if not usage_types:
        usage_types.append("static import only")

    return confidence, usage_types


def audit_dependencies(
    project_path: str,
    dependencies: list[str],
    known_optional: Optional[list[str]] = None,
    project_name: Optional[str] = None,
    history_manager=None
) -> AuditResult:
    """Audit dependencies against actual usage in the project.

    Args:
        project_path: Path to the project.
        dependencies: List of dependency strings (e.g., "requests>=2.28").
        known_optional: List of optional dependency names.
        project_name: Name of the project (to exclude from missing deps).
        history_manager: Optional AuditHistoryManager for tracking resolved issues.

    Returns:
        AuditResult with unused, missing, and all dependencies.
    """
    known_optional = known_optional or []
    imports = scan_imports(project_path)

    is_re_audit = False
    resolved_count = 0
    acknowledged_count = 0

    if history_manager:
        history_manager.record_audit()
        history_summary = history_manager.get_summary()
        is_re_audit = history_summary["total_audits"] > 1
        resolved_count = history_summary["total_resolved"]
        acknowledged_count = history_summary["total_acknowledged"]

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
        usage_types = []

        for imp_name, lines in imports.items():
            imp_normalized = _normalize_package_name(imp_name)
            if imp_normalized == pkg_normalized:
                import_lines.extend(lines)
                usage_types.append("static import")
            if imp_normalized in PACKAGE_ALIASES:
                alias_target = _normalize_package_name(PACKAGE_ALIASES[imp_normalized])
                if alias_target == pkg_normalized:
                    import_lines.extend(lines)
                    usage_types.append(f"alias import ({imp_name})")

        is_used = len(import_lines) > 0
        is_optional = pkg_normalized in {_normalize_package_name(o) for o in known_optional}

        if not is_used:
            confidence, safety_types = _check_dependency_safety(
                project_path, pkg_name, pkg_normalized
            )
            if safety_types and safety_types != ["static import only"]:
                is_used = True
                usage_types.extend(safety_types)
                if "low" not in confidence:
                    confidence = "medium"
        else:
            confidence, _ = _check_dependency_safety(
                project_path, pkg_name, pkg_normalized
            )

        result = UsageResult(
            package_name=pkg_name,
            is_used=is_used,
            import_lines=import_lines,
            is_optional=is_optional,
            confidence=confidence,
            usage_type=usage_types if usage_types else ["no usage detected"],
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

    if history_manager:
        filtered_unused = []
        for u in unused:
            if not (history_manager.is_resolved(u.package_name, "unused") or
                    history_manager.is_acknowledged(u.package_name, "unused")):
                filtered_unused.append(u)
            else:
                resolved_count += 1
        unused = filtered_unused

        filtered_missing = []
        for pkg, files in missing:
            if not (history_manager.is_resolved(pkg, "missing") or
                    history_manager.is_acknowledged(pkg, "missing")):
                filtered_missing.append((pkg, files))
            else:
                acknowledged_count += 1
        missing = filtered_missing

    unused_safe = [u for u in unused if u.confidence == "high"]
    unused_uncertain = [u for u in unused if u.confidence != "high"]

    if is_re_audit:
        prev_resolved = resolved_count + acknowledged_count
        lines_summary = []
        if prev_resolved > 0:
            lines_summary.append(f"{prev_resolved} previously resolved")
        unused_summary = f"{len(unused)} unused ({len(unused_safe)} safe to remove, {len(unused_uncertain)} uncertain)" if unused else "All dependencies used"
        if lines_summary:
            lines_summary.append(unused_summary)
            unused_summary = ", ".join(lines_summary)
    else:
        unused_summary = f"{len(unused)} unused ({len(unused_safe)} safe to remove, {len(unused_uncertain)} uncertain)" if unused else "All dependencies used"

    missing_summary = f"{len(missing)} missing" if missing else "No missing dependencies"

    summary = f"Audit complete: {unused_summary}, {missing_summary}"

    return AuditResult(
        unused_dependencies=unused,
        missing_dependencies=missing,
        all_dependencies=dep_results,
        summary=summary,
        resolved_count=resolved_count,
        acknowledged_count=acknowledged_count,
        is_re_audit=is_re_audit,
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

    if result.is_re_audit:
        total_handled = result.resolved_count + result.acknowledged_count
        lines.append(f"\n[Re-audit: {total_handled} issues previously handled]")
        if result.resolved_count > 0:
            lines.append(f"  - {result.resolved_count} resolved")
        if result.acknowledged_count > 0:
            lines.append(f"  - {result.acknowledged_count} acknowledged")

    unused_safe = [u for u in result.unused_dependencies if u.confidence == "high"]
    unused_uncertain = [u for u in result.unused_dependencies if u.confidence != "high"]

    if result.unused_dependencies:
        lines.append(f"\nUNUSED DEPENDENCIES ({len(result.unused_dependencies)} total):")

        if unused_safe:
            lines.append(f"\n  SAFE TO REMOVE ({len(unused_safe)}):")
            for dep in unused_safe:
                lines.append(f"    [SAFE] {dep.package_name}")

        if unused_uncertain:
            lines.append(f"\n  UNCERTAIN - VERIFY BEFORE REMOVING ({len(unused_uncertain)}):")
            for dep in unused_uncertain:
                usage = ", ".join(dep.usage_type[:2]) if dep.usage_type else "unknown"
                lines.append(f"    [CAUTION:{dep.confidence.upper()}] {dep.package_name}")
                lines.append(f"         Reason: {usage}")
                if dep.import_lines:
                    for fp, ln in dep.import_lines[:2]:
                        lines.append(f"         - {os.path.basename(fp)}:{ln}")

    if result.missing_dependencies:
        lines.append(f"\nMISSING DEPENDENCIES ({len(result.missing_dependencies)}):")
        for pkg, files in result.missing_dependencies:
            lines.append(f"  {pkg}")
            for f in files[:3]:
                lines.append(f"      - {f}")
            if len(files) > 3:
                lines.append(f"      ... and {len(files) - 3} more")

    if not result.unused_dependencies and not result.missing_dependencies:
        lines.append("\nAll dependencies are used and no missing dependencies!")

    lines.append(f"\n{result.summary}")

    return "\n".join(lines)


def remove_unused_dependencies(
    project_path: str,
    unused_dependencies: list[str],
    create_backup: bool = True,
    safe_only: bool = True,
    history_manager=None
) -> tuple[int, list[str], list[str]]:
    """Remove unused dependencies from project files.

    Args:
        project_path: Path to the project.
        unused_dependencies: List of package names to remove.
        create_backup: Whether to create backup files.
        safe_only: Only remove dependencies marked as safe (confidence='high').
        history_manager: Optional AuditHistoryManager to record removals.

    Returns:
        Tuple of (files modified count, list of modified files, list of skipped).
    """
    import shutil
    from .dependency_parser import parse_all

    modified_files = []
    skipped = []

    if safe_only:
        safe_deps = set()
        imports = scan_imports(project_path)

        for dep in unused_dependencies:
            pkg_normalized = _normalize_package_name(dep)
            confidence, _ = _check_dependency_safety(project_path, dep, pkg_normalized)
            if confidence == "high":
                safe_deps.add(dep)
            else:
                skipped.append(f"{dep} (confidence: {confidence})")

        unused_dependencies = list(safe_deps)
        if skipped:
            logger.info(f"Skipped {len(skipped)} dependencies with uncertain usage")

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

    if history_manager and unused_dependencies:
        for dep in unused_dependencies:
            history_manager.mark_resolved(dep, "unused", "removed", modified_files)

    return len(modified_files), modified_files, skipped


def _remove_from_python(content: str, package_name: str) -> str:
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
    dep_normalized = _normalize_package_name(package_name)

    content = re.sub(
        rf"^\s*{re.escape(package_name)}[^\n]*\n",
        "",
        content,
        flags=re.MULTILINE
    )

    return content


def _remove_from_toml(content: str, package_name: str) -> str:
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
