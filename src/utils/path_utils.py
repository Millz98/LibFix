import sys

def get_python_interpreter_path():
    """Returns the path to the currently running Python interpreter."""
    return sys.executable

if __name__ == '__main__':
    print(f"Current Python interpreter: {get_python_interpreter_path()}")