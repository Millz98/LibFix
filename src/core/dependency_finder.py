import os

def find_dependency_files(project_directory):
    """
    Searches the given project directory for common dependency files.

    Args:
        project_directory (str): The path to the Python project directory.

    Returns:
        dict: A dictionary where keys are file types and values are lists of file paths found.
              Example: {'requirements': ['/path/to/project/requirements.txt'],
                        'setup': ['/path/to/project/setup.py'],
                        'pyproject': ['/path/to/project/pyproject.toml']}
    """
    dependency_files = {
        'requirements': [],
        'setup': [],
        'pyproject': []
    }

    for root, _, files in os.walk(project_directory):
        for file in files:
            if file == 'requirements.txt':
                dependency_files['requirements'].append(os.path.join(root, file))
            elif file == 'setup.py':
                dependency_files['setup'].append(os.path.join(root, file))
            elif file == 'pyproject.toml':
                dependency_files['pyproject'].append(os.path.join(root, file))

    return dependency_files

if __name__ == '__main__':
    # Example usage (for testing this module directly)
    test_project = '/path/to/your/test/project'  # Replace with an actual path for testing
    if os.path.exists(test_project):
        found_files = find_dependency_files(test_project)
        print("Found dependency files:")
        for file_type, files in found_files.items():
            for file_path in files:
                print(f"- {file_type}: {file_path}")
    else:
        print(f"Test project directory '{test_project}' not found.")