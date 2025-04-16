import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QFileDialog, QLabel, QVBoxLayout, QWidget, QListWidget
from PyQt6.QtCore import Qt
import qdarkstyle
from .core.dependency_finder import find_dependency_files
from .utils.path_utils import get_python_interpreter_path


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LibFix")
        self.setGeometry(100, 100, 400, 300) # Increased height

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.select_button = QPushButton("Select Python Project")
        self.select_button.clicked.connect(self.select_project_directory)
        self.select_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; /* Green */
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.layout.addWidget(self.select_button)

        self.project_label = QLabel("No project selected")
        self.project_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #555;
                margin-top: 15px;
            }
        """)
        self.project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.project_label)

        self.dependency_list_label = QLabel("Found Dependency Files:")
        self.dependency_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.dependency_list_label)

        self.dependency_list_widget = QListWidget()
        self.layout.addWidget(self.dependency_list_widget)

        self.central_widget.setLayout(self.layout)
        self.project_directory = None
        self.python_interpreter_path = get_python_interpreter_path()

        print(f"LibFix is running with: {self.python_interpreter_path}")

    def select_project_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Python Project Directory")
        if directory:
            self.project_directory = directory
            self.project_label.setText(f"Selected Project: {self.project_directory}")
            print(f"Selected project directory: {self.project_directory}")
            self.find_and_display_dependencies()

    def find_and_display_dependencies(self):
        if self.project_directory:
            self.dependency_list_widget.clear() # Clear previous results
            found_files = find_dependency_files(self.project_directory)
            for file_type, files in found_files.items():
                for file_path in files:
                    self.dependency_list_widget.addItem(f"[{file_type.capitalize()}] {os.path.basename(file_path)}")
                if not any(found_files.values()):
                    self.dependency_list_widget.addItem("No dependency files found in this project.")
            else:
                self.dependency_list_widget.addItem("Please select a project directory first.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='PyQt6'))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())