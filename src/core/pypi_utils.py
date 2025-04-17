import requests
import json

def get_package_info_from_pypi(package_name):
    """
    Fetches package information from the PyPI JSON API.

    Args:
        package_name (str): The name of the package.

    Returns:
        dict or None: A dictionary containing the package information if successful,
                       None if there was an error (e.g., package not found, network issue).
    """
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching info for {package_name} from PyPI: {e}")
        return None

if __name__ == '__main__':
    # Example usage
    package = "requests"
    info = get_package_info_from_pypi(package)
    if info:
        print(f"Information for {package}:")
        print(json.dumps(info, indent=4))
    else:
        print(f"Could not retrieve information for {package}.")