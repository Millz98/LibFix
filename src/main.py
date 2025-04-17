# Import necessary modules from the standard library
import sys
import os
import threading

# Import necessary modules from PyQt6 for building the GUI
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QFileDialog,
    QLabel,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QMessageBox
)
from PyQt6.QtCore import Qt

# Import qdarkstyle for applying a dark theme to the application
import qdarkstyle

# Import functions from local modules within the project
from .core.dependency_finder import find_dependency_files
from .utils.path_utils import get_python_interpreter_path
from .core.dependency_parser import parse_requirements_txt, parse_setup_py, parse_pyproject_toml
from .core.pypi_utils import get_package_info_from_pypi
from .core.dependency_analyzer import is_potentially_inactive  # Import the new function

class MainWindow(QMainWindow):
    """
    The main application window for LibFix.
    Allows users to select a Python project directory and view its dependencies
    along with the latest version from PyPI and potential inactivity status.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LibFix")
        self.setGeometry(100, 100, 600, 400)  # Increased width for more info

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop) # Align top for the list

        self.select_button = QPushButton("Select Python Project")
        self.select_button.clicked.connect(self.select_project_directory)
        self.select_button.setStyleSheet("""
            QPushButton {
                background-color: #625e5d ; /* Darker button color */
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #919898; /* Lighter button color on hover */
            }
        """)
        self.layout.addWidget(self.select_button)

        self.project_label = QLabel("No project selected")
        self.project_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #555; /* A dark gray color */
                margin-top: 15px; /* Add some space above the label */
            }
        """)
        self.project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.project_label)

        self.dependency_list_label = QLabel("Dependencies (Latest PyPI Version, Inactivity):")
        self.dependency_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.dependency_list_label)

        self.dependency_list_widget = QListWidget()
        self.layout.addWidget(self.dependency_list_widget)

        self.central_widget.setLayout(self.layout)
        self.project_directory = None
        self.python_interpreter_path = get_python_interpreter_path()
        self.dependency_files = {}
        self.dependencies_with_info = {} # Store dependencies and their PyPI info

        print(f"LibFix is running with: {self.python_interpreter_path}")

    def select_project_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Python Project Directory")
        if directory:
            self.project_directory = directory
            self.project_label.setText(f"Selected Project: {self.project_directory}")
            print(f"Selected project directory: {self.project_directory}")
            self.find_and_parse_dependencies() # Combined find and parse

    def find_and_parse_dependencies(self):
        if self.project_directory:
            self.dependency_list_widget.clear()
            self.dependency_list_widget.addItem("Finding and parsing dependencies...")
            self.dependency_files = find_dependency_files(self.project_directory)
            all_dependencies = set() # Use a set to automatically handle duplicates

            for file_type, files in self.dependency_files.items():
                for file_path in files:
                    if file_type == 'requirements':
                        dependencies = parse_requirements_txt(file_path)
                        all_dependencies.update(dependencies)
                    elif file_type == 'setup':
                        dependencies = parse_setup_py(file_path)
                        all_dependencies.update(dependencies)
                    elif file_type == 'pyproject':
                        dependencies = parse_pyproject_toml(file_path)
                        all_dependencies.update(dependencies)

            if all_dependencies:
                self.dependency_list_widget.addItem("Fetching latest versions and analyzing activity from PyPI...")
                # Start a thread to fetch PyPI info and analyze inactivity without blocking the UI
                threading.Thread(target=self.fetch_pypi_info_and_analyze, args=(list(all_dependencies),)).start()
            else:
                self.dependency_list_widget.addItem("No dependencies found in this project.")
        else:
            self.dependency_list_widget.addItem("Please select a project directory first.")

    def fetch_pypi_info_and_analyze(self, dependencies):
        self.dependencies_with_info = {}
        for dep in dependencies:
            package_name = self.extract_package_name(dep) # Extract just the name
            info = get_package_info_from_pypi(package_name)
            self.dependencies_with_info[dep] = info
        # Update the UI from the main thread after fetching info and analyzing
        self.update_dependency_list_with_info()

    def extract_package_name(self, dependency_string):
        """Simple extraction of package name from dependency string (e.g., 'requests>=2.20' -> 'requests')."""
        parts = dependency_string.split('>', 1)[0].split('<', 1)[0].split('=', 1)[0].split('!', 1)[0]
        return parts.strip()

    def update_dependency_list_with_info(self):
        self.dependency_list_widget.clear()
        if self.dependencies_with_info:
            for dep, info in self.dependencies_with_info.items():
                latest_version = "N/A"
                inactivity_status = ""
                inactivity_reason = ""

                if info and 'info' in info and 'version' in info['info']:
                    latest_version = info['info']['version']
                    inactive, reason = is_potentially_inactive(info)
                    if inactive:
                        inactivity_status = " [INACTIVE?]"
                        inactivity_reason = f" (Reason: {reason})"

                self.dependency_list_widget.addItem(f"{dep} (Latest: {latest_version}){inactivity_status}{inactivity_reason}")
        elif self.project_directory and not any(find_dependency_files(self.project_directory).values()):
            self.dependency_list_widget.addItem("No dependency files found in this project.")
        elif self.project_directory:
            self.dependency_list_widget.addItem("No dependencies listed in the found files.")
        else:
            self.dependency_list_widget.addItem("Please select a project directory first.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='PyQt6'))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())