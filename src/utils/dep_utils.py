"""Shared utility functions for dependency string parsing."""

__all__ = ["extract_package_name"]


def extract_package_name(dependency_string: str) -> str:
    """Extract just the package name from a dependency string.

    Strips version specifiers, extras, markers, and environment markers.

    Examples:
        "requests>=2.28" -> "requests"
        "psycopg2[binary]" -> "psycopg2"
        "toml; python_version < '3.11'" -> "toml"
        "Django>=4.0,<5.0" -> "Django"
    """
    name = dependency_string.split('>', 1)[0].split('<', 1)[0].split('=', 1)[0].split('!', 1)[0]
    name = name.split('[', 1)[0].split(';', 1)[0]
    return name.strip()
