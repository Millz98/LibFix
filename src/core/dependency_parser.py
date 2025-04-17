import os
import re
import toml

def parse_requirements_txt(file_path):
    """Parses a requirements.txt file and returns a list of dependencies."""
    dependencies = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    dependencies.append(line)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    return dependencies

def parse_setup_py(file_path):
    """Parses a setup.py file and returns a list of install_requires."""
    dependencies = []
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            match = re.search(r"install_requires=\[([^\]]*)\]", content)
            if match:
                deps_str = match.group(1).strip()
                # Simple splitting by comma, might need more robust handling for complex cases
                dependencies = [dep.strip().strip("'").strip('"') for dep in deps_str.split(',')]
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    return dependencies

def parse_pyproject_toml(file_path):
    """Parses a pyproject.toml file and returns a list of dependencies (for Poetry)."""
    dependencies = []
    try:
        with open(file_path, 'r') as f:
            data = toml.load(f)
            if 'tool' in data and 'poetry' in data['tool'] and 'dependencies' in data['tool']['poetry']:
                for package, version in data['tool']['poetry']['dependencies'].items():
                    if package != 'python':  # Exclude Python version constraint
                        dependencies.append(f"{package}{version if version != '*' else ''}")
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except toml.TomlDecodeError:
        print(f"Error: Could not decode TOML in {file_path}")
    return dependencies

if __name__ == '__main__':
    # Example usage (for testing) - replace with actual file paths
    requirements_file = '/path/to/your/test/project/requirements.txt'
    setup_file = '/path/to/your/test/project/setup.py'
    pyproject_file = '/path/to/your/test/project/pyproject.toml'

    if os.path.exists(requirements_file):
        print(f"Requirements: {parse_requirements_txt(requirements_file)}")
    if os.path.exists(setup_file):
        print(f"Setup.py deps: {parse_setup_py(setup_file)}")
    if os.path.exists(pyproject_file):
        print(f"Pyproject.toml deps: {parse_pyproject_toml(pyproject_file)}")