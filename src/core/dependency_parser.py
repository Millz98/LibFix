import os
import re
import toml

def parse_requirements_txt(file_path):
    """
    Parses a requirements.txt file and returns a list of dependencies.

    Args:
        file_path (str): The path to the requirements.txt file.

    Returns:
        list: A list of dependency strings, or an empty list if the file is not found.
    """
    dependencies = []
    try:
        with open(file_path, 'r') as f:
            # Iterate through each line in the file
            for line in f:
                # Remove leading/trailing whitespace
                line = line.strip()
                # Check if the line is not empty and not a comment
                if line and not line.startswith('#'):
                    # Add the dependency to the list
                    dependencies.append(line)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    return dependencies

def parse_setup_py(file_path):
    """
    Parses a setup.py file and returns a list of dependencies from install_requires.

    Args:
        file_path (str): The path to the setup.py file.

    Returns:
        list: A list of dependency strings, or an empty list if the file is not found or install_requires is not present.
    """
    dependencies = []
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            # Search for the install_requires section using a regular expression
            match = re.search(r"install_requires=\[([^\]]*)\]", content)
            if match:
                # Extract the string containing the dependencies
                deps_str = match.group(1).strip()
                # Split the string by commas and clean up each dependency string
                dependencies = [dep.strip().strip("'").strip('"') for dep in deps_str.split(',')]
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    return dependencies

def parse_pyproject_toml(file_path):
    """
    Parses a pyproject.toml file and returns a list of dependencies (specifically for Poetry projects).

    Args:
        file_path (str): The path to the pyproject.toml file.

    Returns:
        list: A list of dependency strings, or an empty list if the file is not found or not a Poetry project.
    """
    dependencies = []
    try:
        with open(file_path, 'r') as f:
            # Load the TOML data
            data = toml.load(f)
            # Check if it's a Poetry project and has dependencies
            if 'tool' in data and 'poetry' in data['tool'] and 'dependencies' in data['tool']['poetry']:
                # Iterate through the dependencies
                for package, version in data['tool']['poetry']['dependencies'].items():
                    # Exclude the Python version constraint
                    if package != 'python':
                        # Format the dependency string
                        dependencies.append(f"{package}{version if version != '*' else ''}")
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except toml.TomlDecodeError:
        print(f"Error: Could not decode TOML in {file_path}")
    return dependencies

# Example usage (for testing) - replace with actual file paths
if __name__ == '__main__':
    # Define test file paths (replace with your actual test files)
    requirements_file = '/path/to/your/test/project/requirements.txt'
    setup_file = '/path/to/your/test/project/setup.py'
    pyproject_file = '/path/to/your/test/project/pyproject.toml'

    # Check if the files exist and parse them
    if os.path.exists(requirements_file):
        print(f"Requirements: {parse_requirements_txt(requirements_file)}")
    if os.path.exists(setup_file):
        print(f"Setup.py deps: {parse_setup_py(setup_file)}")
    if os.path.exists(pyproject_file):
        print(f"Pyproject.toml deps: {parse_pyproject_toml(pyproject_file)}")