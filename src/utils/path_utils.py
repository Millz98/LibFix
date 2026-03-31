import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def get_python_interpreter_path() -> str:
    """Returns the path to the currently running Python interpreter."""
    path = sys.executable
    logger.debug(f"Python interpreter path: {path}")
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(f"Current Python interpreter: {get_python_interpreter_path()}")
