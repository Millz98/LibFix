# Import necessary modules from the standard library
import sys  # Provides access to system-specific parameters and functions (like command line arguments, exit)
import os   # Provides a way of using operating system dependent functionality (like path manipulation)

# Import necessary modules from PyQt6 for building the GUI
from PyQt6.QtWidgets import (
    QApplication,      # Manages the GUI application's control flow and main settings
    QMainWindow,       # Represents the main window of the application
    QPushButton,       # A command button widget
    QFileDialog,       # Provides a dialog for selecting files or directories
    QLabel,            # A widget for displaying text or images
    QVBoxLayout,       # A layout manager that arranges widgets vertically
    QWidget,           # The base class for all user interface objects
    QListWidget        # A widget that displays a list of items
)
from PyQt6.QtCore import Qt # Contains core non-GUI functionality, including alignment flags

# Import qdarkstyle for applying a dark theme to the application
import qdarkstyle

# Import functions from local modules within the project
from .core.dependency_finder import find_dependency_files # Function to find dependency files in a project
from .utils.path_utils import get_python_interpreter_path # Function to get the path of the current Python interpreter
from .core.dependency_parser import parse_requirements_txt, parse_setup_py, parse_pyproject_toml


# Define the main window class, inheriting from QMainWindow
class MainWindow(QMainWindow):
    """
    The main application window for LibFix.
    Allows users to select a Python project directory and view its dependency files.
    """
    def __init__(self):
        """
        Initializes the MainWindow instance.
        Sets up the window properties, layout, and widgets.
        """
        # Call the constructor of the parent class (QMainWindow)
        super().__init__()

        # Set the title that appears in the window's title bar
        self.setWindowTitle("LibFix")
        # Set the initial position (x=100, y=100) and size (width=400, height=300) of the window
        self.setGeometry(100, 100, 400, 300) # Increased height

        # Create a central widget that will hold all other widgets and layouts
        self.central_widget = QWidget()
        # Set this widget as the central content area of the QMainWindow
        self.setCentralWidget(self.central_widget)

        # Create a vertical box layout to arrange widgets from top to bottom
        self.layout = QVBoxLayout()
        # Align the widgets within the layout to the center
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create a button labeled "Select Python Project"
        self.select_button = QPushButton("Select Python Project")
        # Connect the button's 'clicked' signal to the 'select_project_directory' method
        self.select_button.clicked.connect(self.select_project_directory)
        # Apply custom styling to the button using CSS-like syntax
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
        # Add the button to the vertical layout
        self.layout.addWidget(self.select_button)

        # Create a label to display the path of the selected project
        self.project_label = QLabel("No project selected")
        # Apply custom styling to the label
        self.project_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #555; /* A dark gray color */
                margin-top: 15px; /* Add some space above the label */
            }
        """)
        # Align the text within the label to the center
        self.project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Add the label to the vertical layout
        self.layout.addWidget(self.project_label)

        # Create a label to act as a title for the dependency list
        self.dependency_list_label = QLabel("Found Dependency Files:")
        # Align the text within the label to the center
        self.dependency_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Add the label to the vertical layout
        self.layout.addWidget(self.dependency_list_label)

        # Create a list widget to display the found dependency files
        self.dependency_list_widget = QListWidget()
        # Add the list widget to the vertical layout
        self.layout.addWidget(self.dependency_list_widget)

        # Set the created vertical layout as the layout for the central widget
        self.central_widget.setLayout(self.layout)

        # Initialize the attribute to store the selected project directory path (None initially)
        self.project_directory = None
        # Get the path of the Python interpreter currently running this script
        self.python_interpreter_path = get_python_interpreter_path()
        # Initialize a dictionary to store the paths of found dependency files
        self.dependency_files = {}

        # Print the path of the Python interpreter being used to the console for debugging/info
        print(f"LibFix is running with: {self.python_interpreter_path}")

    def select_project_directory(self):
        """
        Opens a dialog for the user to select a directory.
        If a directory is selected, updates the project path and triggers dependency finding.
        """
        # Open a standard dialog asking the user to select an existing directory
        # 'self' is the parent window, "Select Python Project Directory" is the dialog title
        directory = QFileDialog.getExistingDirectory(self, "Select Python Project Directory")

        # Check if the user selected a directory (and didn't cancel the dialog)
        if directory:
            # Store the selected directory path in the instance attribute
            self.project_directory = directory
            # Update the project label to show the selected path
            self.project_label.setText(f"Selected Project: {self.project_directory}")
            # Print the selected path to the console for debugging/info
            print(f"Selected project directory: {self.project_directory}")
            # Call the method to find and display dependency files for the selected directory
            self.find_and_display_dependencies()

    def find_and_display_dependencies(self):
        """
        Finds dependency files (like requirements.txt, pyproject.toml) in the selected
        project directory and displays them in the list widget, then parses and displays the dependencies.
        """
        # Check if a project directory has been selected
        if self.project_directory:
            # Clear any items currently displayed in the list widget
            self.dependency_list_widget.clear()
            # Call the imported function to find dependency files in the selected directory
            self.dependency_files = find_dependency_files(self.project_directory)
            all_dependencies = []

            # Iterate through the dictionary of found files (key=file_type, value=list_of_paths)
            for file_type, files in self.dependency_files.items():
                # Iterate through the list of file paths for the current file type
                for file_path in files:
                    # Add an item to the list widget, formatting it with the type and filename
                    # os.path.basename extracts the filename from the full path
                    self.dependency_list_widget.addItem(f"[{file_type.capitalize()}] {os.path.basename(file_path)}")
                    # Parse the dependencies based on the file type
                    if file_type == 'requirements':
                        dependencies = parse_requirements_txt(file_path)
                        all_dependencies.extend(dependencies)
                    elif file_type == 'setup':
                        dependencies = parse_setup_py(file_path)
                        all_dependencies.extend(dependencies)
                    elif file_type == 'pyproject':
                        dependencies = parse_pyproject_toml(file_path)
                        all_dependencies.extend(dependencies)

            # Display the extracted dependencies
            if all_dependencies:
                self.dependency_list_widget.addItem("\n--- Dependencies ---")
                # Add each unique dependency to the list widget, sorted alphabetically
                for dep in sorted(list(set(all_dependencies))):
                    self.dependency_list_widget.addItem(f"- {dep}")
            elif not any(self.dependency_files.values()):
                # If no dependency files were found, display a message
                self.dependency_list_widget.addItem("No dependency files found in this project.")
            else:
                # If dependency files were found but no dependencies were extracted
                self.dependency_list_widget.addItem("No dependencies found in the dependency files.")

        else:
            # If no project directory has been selected yet, clear the list and show a message
            self.dependency_list_widget.clear()
            self.dependency_list_widget.addItem("Please select a project directory first.")


# This block ensures the code runs only when the script is executed directly
# (not when imported as a module)
if __name__ == "__main__":
    # Create a QApplication instance, necessary for any PyQt application
    # sys.argv allows passing command-line arguments to the application
    app = QApplication(sys.argv)

    # Apply the dark stylesheet from the qdarkstyle library to the entire application
    # 'qt_api='PyQt6'' specifies that we are using PyQt6
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='PyQt6'))

    # Create an instance of our MainWindow class
    window = MainWindow()
    # Make the main window visible on the screen
    window.show()

    # Start the application's event loop. The application will wait for user interaction.
    # sys.exit ensures a clean exit, passing the application's exit code to the system.
    sys.exit(app.exec())