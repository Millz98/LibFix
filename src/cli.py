import argparse
import logging
import sys
import json
from pathlib import Path

from .core.dependency_finder import find_dependency_files
from .core.dependency_parser import parse_all
from .core.pypi_utils import get_package_info_from_pypi, clear_cache
from .core.dependency_analyzer import is_potentially_inactive, INACTIVITY_THRESHOLD_YEARS


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        stream=sys.stdout
    )


def analyze_project(project_path: str, threshold: float, output_format: str, show_all: bool) -> list[dict]:
    """Analyze a project for dependency information."""
    logger = logging.getLogger(__name__)
    results = []

    logger.info(f"Scanning: {project_path}")
    dependency_files = find_dependency_files(project_path)
    all_dependencies = set()

    file_type_map = {
        'requirements': 'requirements.txt',
        'setup': 'setup.py',
        'setup_cfg': 'setup.cfg',
        'pyproject': 'pyproject.toml',
        'pipfile': 'Pipfile',
    }

    for file_type, files in dependency_files.items():
        for file_path in files:
            deps = parse_all(file_path)
            all_dependencies.update(deps)
            logger.debug(f"  {file_type_map.get(file_type, file_type)}: {len(deps)} deps")

    if not all_dependencies:
        logger.warning("No dependencies found")
        return results

    logger.info(f"Analyzing {len(all_dependencies)} dependencies...")

    for dep in sorted(all_dependencies):
        package_name = _extract_package_name(dep)
        info = get_package_info_from_pypi(package_name)

        result = {
            'dependency': dep,
            'package': package_name,
            'latest_version': 'N/A',
            'inactive': False,
            'reason': '',
            'alternatives': [],
        }

        if info and 'info' in info:
            version = info['info'].get('version')
            if version:
                result['latest_version'] = version

            inactive, reason, alternatives = is_potentially_inactive(info, package_name)
            result['inactive'] = inactive
            result['reason'] = reason
            result['alternatives'] = alternatives

        if show_all or result['inactive']:
            results.append(result)

    return results


def _extract_package_name(dependency_string: str) -> str:
    parts = dependency_string.split('>', 1)[0].split('<', 1)[0].split('=', 1)[0].split('!', 1)[0]
    return parts.strip()


def print_results(results: list[dict], output_format: str) -> None:
    """Print analysis results in the specified format."""
    if output_format == 'json':
        print(json.dumps(results, indent=2))
    elif output_format == 'compact':
        for r in results:
            status = "INACTIVE" if r['inactive'] else "ok"
            alt = f" -> {', '.join(r['alternatives'])}" if r['alternatives'] else ""
            print(f"[{status}] {r['dependency']} ({r['latest_version']}){alt}")
    else:
        for r in results:
            print(f"\n{r['dependency']}")
            print(f"  Latest: {r['latest_version']}")
            if r['inactive']:
                print(f"  Status: INACTIVE")
                print(f"  Reason: {r['reason']}")
                if r['alternatives']:
                    print(f"  Alternatives: {', '.join(r['alternatives'])}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LibFix - Python Dependency Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  libfix analyze /path/to/project
  libfix analyze . --output json
  libfix analyze . --show-all --output compact
  libfix cache clear
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    analyze_parser = subparsers.add_parser('analyze', help='Analyze a Python project')
    analyze_parser.add_argument('project', nargs='?', default='.', help='Project directory (default: .)')
    analyze_parser.add_argument('-t', '--threshold', type=float, default=INACTIVITY_THRESHOLD_YEARS,
                                 help=f'Inactivity threshold in years (default: {INACTIVITY_THRESHOLD_YEARS})')
    analyze_parser.add_argument('-o', '--output', choices=['text', 'json', 'compact'], default='text',
                                help='Output format')
    analyze_parser.add_argument('-a', '--show-all', action='store_true',
                                help='Show all packages, not just inactive ones')
    analyze_parser.add_argument('-q', '--quiet', action='store_true', help='Suppress non-error output')

    cache_parser = subparsers.add_parser('cache', help='Manage cache')
    cache_parser.add_argument('action', choices=['clear', 'info'], help='Cache action')

    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == 'cache':
        if args.action == 'clear':
            clear_cache()
            print("Cache cleared")
            return 0
        elif args.action == 'info':
            from .core.cache import get_cache
            cache = get_cache()
            cache_files = list(cache.cache_dir.glob("*.json"))
            print(f"Cache directory: {cache.cache_dir}")
            print(f"Cached packages: {len(cache_files)}")
            return 0

    if args.command == 'analyze' or args.command is None:
        if args.command is None:
            project_path = args.project if len(sys.argv) > 1 else '.'
        else:
            project_path = args.project

        results = analyze_project(
            project_path,
            args.threshold if hasattr(args, 'threshold') else INACTIVITY_THRESHOLD_YEARS,
            args.output if hasattr(args, 'output') else 'text',
            args.show_all if hasattr(args, 'show_all') else False
        )

        inactive_count = sum(1 for r in results if r['inactive'])
        if not args.quiet if hasattr(args, 'quiet') else False:
            print(f"\nFound {inactive_count} potentially inactive packages")

        print_results(results, args.output if hasattr(args, 'output') else 'text')
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
