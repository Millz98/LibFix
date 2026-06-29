import logging
import os
import sys
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSortFilterProxyModel, QTimer
from PyQt6.QtGui import QColor, QFont, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QFileDialog,
    QLabel,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QProgressBar,
    QHBoxLayout,
    QDialog,
    QComboBox,
    QDialogButtonBox,
    QMessageBox,
    QTextEdit,
    QInputDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QGroupBox,
    QStatusBar,
    QToolBar,
    QAbstractItemView,
    QMenu,
)
import qdarkstyle

from .core.dependency_finder import find_dependency_files
from .utils.path_utils import get_python_interpreter_path
from .core.dependency_parser import parse_all
from .core.pypi_utils import get_package_info_from_pypi
from .core.dependency_analyzer import is_potentially_inactive
from .core.dependency_replacer import replace_dependency
from .utils.dep_utils import extract_package_name
from .core.audit_history import load_audit_history

logger = logging.getLogger(__name__)


class DependencyFetcherThread(QThread):
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(dict)

    def __init__(self, dependencies: list[str]) -> None:
        super().__init__()
        self.dependencies = dependencies

    def run(self) -> None:
        deps_with_info: dict[str, Optional[dict]] = {}
        total = len(self.dependencies)
        for i, dep in enumerate(self.dependencies):
            if self.isInterruptionRequested():
                break
            package_name = extract_package_name(dep)
            info = get_package_info_from_pypi(package_name)
            deps_with_info[dep] = info
            self.progress_signal.emit(i + 1, total)
        self.finished_signal.emit(deps_with_info)


class ReplacementThread(QThread):
    progress_signal = pyqtSignal(str, bool)
    finished_signal = pyqtSignal()

    def __init__(self, project_path: str, old_dep: str, new_dep: str) -> None:
        super().__init__()
        self.project_path = project_path
        self.old_dep = old_dep
        self.new_dep = new_dep

    def run(self) -> None:
        from .core.dependency_replacer import replace_dependency
        result = replace_dependency(self.project_path, self.old_dep, self.new_dep)
        self.progress_signal.emit(result.message, result.success)
        self.finished_signal.emit()


class AlternativeSelectionDialog(QDialog):
    def __init__(self, parent: QWidget, dep: str, alternatives: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Select Alternative")
        self.dep = dep
        self.selected_alternative: Optional[str] = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Replace: <b>{dep}</b>"))
        layout.addWidget(QLabel("With:"))

        self.combo = QComboBox()
        self.combo.addItems(alternatives)
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected(self) -> Optional[str]:
        if self.exec() == QDialog.DialogCode.Accepted:
            return self.combo.currentText()
        return None


class AuditDialog(QDialog):
    def __init__(self, parent: QWidget, project_path: str, dependencies: list[str]):
        super().__init__(parent)
        self.project_path = project_path
        self.dependencies = dependencies
        self.audit_result = None
        self.history_manager = None

        self.setWindowTitle("Dependency Usage Audit")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

        button_layout = QHBoxLayout()

        self.remove_unused_btn = QPushButton("Remove Unused Dependencies")
        self.remove_unused_btn.clicked.connect(self._remove_unused)
        self.remove_unused_btn.setEnabled(False)
        button_layout.addWidget(self.remove_unused_btn)

        self.add_missing_btn = QPushButton("Add to Requirements")
        self.add_missing_btn.clicked.connect(self._add_missing)
        self.add_missing_btn.setEnabled(False)
        button_layout.addWidget(self.add_missing_btn)

        self.integrate_btn = QPushButton("Full Integration")
        self.integrate_btn.clicked.connect(self._integrate_all)
        self.integrate_btn.setEnabled(False)
        button_layout.addWidget(self.integrate_btn)

        self.acknowledge_btn = QPushButton("Acknowledge...")
        self.acknowledge_btn.clicked.connect(self._acknowledge_issue)
        self.acknowledge_btn.setEnabled(False)
        button_layout.addWidget(self.acknowledge_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        self._run_audit()

    def _run_audit(self) -> None:
        from .core.dependency_auditor import audit_dependencies, generate_audit_report
        from .core.audit_history import load_audit_history

        self.text_area.append("Scanning project for dependency usage...\n")

        self.history_manager = load_audit_history(self.project_path)
        self.audit_result = audit_dependencies(
            self.project_path,
            self.dependencies,
            history_manager=self.history_manager
        )

        report = generate_audit_report(self.audit_result)
        self.text_area.setPlainText(report)

        self.remove_unused_btn.setEnabled(len(self.audit_result.unused_dependencies) > 0)
        self.add_missing_btn.setEnabled(len(self.audit_result.missing_dependencies) > 0)
        self.integrate_btn.setEnabled(len(self.audit_result.missing_dependencies) > 0)
        self.acknowledge_btn.setEnabled(
            len(self.audit_result.unused_dependencies) > 0 or
            len(self.audit_result.missing_dependencies) > 0
        )

    def _remove_unused(self) -> None:
        from .core.dependency_auditor import remove_unused_dependencies

        if not self.audit_result or not self.audit_result.unused_dependencies:
            return

        unused_safe = [dep.package_name for dep in self.audit_result.unused_dependencies if dep.confidence == "high"]
        unused_uncertain = [dep.package_name for dep in self.audit_result.unused_dependencies if dep.confidence != "high"]

        if not unused_safe:
            self.text_area.append("\n\nNo dependencies are safe to remove automatically.")
            if unused_uncertain:
                self.text_area.append(f"Found {len(unused_uncertain)} dependencies with uncertain usage - please verify manually.")
            return

        reply = QMessageBox.question(
            self,
            "Remove Unused Dependencies",
            f"Remove {len(unused_safe)} safe unused dependencies?\n\nSafe: {', '.join(unused_safe[:5])}{'...' if len(unused_safe) > 5 else ''}\n\n{len(unused_uncertain)} uncertain dependencies will be skipped.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            count, files, skipped = remove_unused_dependencies(
                self.project_path, unused_safe, safe_only=True, history_manager=self.history_manager
            )
            self.text_area.append(f"\n\nRemoved dependencies from {count} file(s):")
            for f in files:
                self.text_area.append(f"  • {f}")
            if skipped:
                self.text_area.append(f"\nSkipped {len(skipped)} uncertain dependencies")
                for s in skipped[:5]:
                    self.text_area.append(f"  • {s}")

            self.remove_unused_btn.setEnabled(False)
            self.acknowledge_btn.setEnabled(False)

    def _acknowledge_issue(self) -> None:
        if not self.history_manager:
            return

        unused = [dep.package_name for dep in self.audit_result.unused_dependencies] if self.audit_result else []
        missing = [pkg for pkg, _ in self.audit_result.missing_dependencies] if self.audit_result else []

        all_items = [(f"unused: {p}", p, "unused") for p in unused]
        all_items += [(f"missing: {p}", p, "missing") for p in missing]

        if not all_items:
            return

        msg = "Select an issue to acknowledge (mark as 'will not fix'):\n\n"
        msg += "\n".join([f"{i+1}. {item[0]}" for i, item in enumerate(all_items)])
        msg += "\n\nEnter number (or 0 to cancel):"

        num, ok = QInputDialog.getInt(self, "Acknowledge Issue", msg, 0, 0, len(all_items))
        if not ok or num == 0:
            return

        _, pkg_name, issue_type = all_items[num - 1]
        reason, reason_ok = QInputDialog.getText(self, "Acknowledge Issue", "Reason (optional):")
        if not reason_ok:
            reason = ""

        self.history_manager.acknowledge(pkg_name, issue_type, reason)
        self.text_area.append(f"\nAcknowledged: {issue_type}: {pkg_name}")
        if reason:
            self.text_area.append(f"  Reason: {reason}")

        self._run_audit()

    def _add_missing(self) -> None:
        from .core.dependency_auditor import add_missing_dependencies

        if not self.audit_result or not self.audit_result.missing_dependencies:
            return

        missing = [pkg for pkg, _ in self.audit_result.missing_dependencies]

        reply = QMessageBox.question(
            self,
            "Add Missing Dependencies",
            f"Add {len(missing)} missing dependencies to requirements.txt?\n\n{', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            count, files = add_missing_dependencies(self.project_path, missing)
            if count > 0:
                self.text_area.append(f"\n\nAdded dependencies to {count} file(s):")
                for f in files:
                    self.text_area.append(f"  • {f}")

                if self.history_manager:
                    for pkg in missing:
                        self.history_manager.mark_resolved(pkg, "missing", "added_to_requirements")

                self.add_missing_btn.setEnabled(False)
            else:
                self.text_area.append("\n\nNo requirements.txt found. Cannot add dependencies.")

    def _integrate_all(self) -> None:
        from .core.dependency_integrator import integrate_missing_dependencies
        from .core.dependency_auditor import remove_unused_dependencies

        if not self.audit_result:
            return

        missing = self.audit_result.missing_dependencies
        unused_safe = [dep.package_name for dep in self.audit_result.unused_dependencies if dep.confidence == "high"]
        unused_uncertain = [dep.package_name for dep in self.audit_result.unused_dependencies if dep.confidence != "high"]

        if not missing and not unused_safe:
            self.text_area.append("\n\nNothing to integrate or remove.")
            return

        msg_parts = []
        if missing:
            msg_parts.append(f"1. Install {len(missing)} missing packages via pip")
            msg_parts.append(f"2. Add import statements to source files")
            msg_parts.append(f"3. Add to requirements.txt")
        if unused_safe:
            msg_parts.append(f"\n4. Remove {len(unused_safe)} unused packages (SAFE)")
            msg_parts.append(f"   {', '.join(unused_safe[:3])}{'...' if len(unused_safe) > 3 else ''}")
        if unused_uncertain:
            msg_parts.append(f"\nNote: {len(unused_uncertain)} uncertain deps will be skipped")

        reply = QMessageBox.question(
            self,
            "Full Integration",
            "\n".join(msg_parts) + "\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if missing:
            self.text_area.append("\n\nIntegrating dependencies...")

            results = integrate_missing_dependencies(
                self.project_path,
                missing,
                install=True
            )

            success_count = sum(1 for r in results if r.success)
            self.text_area.append(f"\nIntegration complete: {success_count}/{len(results)} successful")

            for result in results:
                status = "OK" if result.success else "FAILED"
                self.text_area.append(f"  [{status}] {result.package}")
                if result.installed:
                    self.text_area.append(f"      Installed: {result.package}")
                if result.imports_added:
                    for file_path, _ in result.imports_added:
                        self.text_area.append(f"      Added import to: {os.path.basename(file_path)}")
                if result.errors:
                    for error in result.errors:
                        self.text_area.append(f"      Error: {error[:80]}")

                if result.success and self.history_manager:
                    self.history_manager.mark_resolved(result.package, "missing", "full_integration")

        if unused_safe:
            self.text_area.append("\n\nRemoving unused dependencies...")

            count, files, skipped = remove_unused_dependencies(
                self.project_path, unused_safe, safe_only=True, history_manager=self.history_manager
            )

            self.text_area.append(f"\nRemoved from {count} file(s):")
            for f in files:
                self.text_area.append(f"  • {os.path.basename(f)}")
            if skipped:
                self.text_area.append(f"\nSkipped {len(skipped)} uncertain dependencies")

        self.add_missing_btn.setEnabled(False)
        self.integrate_btn.setEnabled(False)
        self.acknowledge_btn.setEnabled(False)
        self.remove_unused_btn.setEnabled(False)


class MigrationGuideDialog(QDialog):
    def __init__(self, parent: QWidget, old_package: str, new_package: str, project_path: str):
        super().__init__(parent)
        self.old_package = old_package
        self.new_package = new_package
        self.project_path = project_path
        self.replacements_made = False

        self.setWindowTitle(f"Migration Guide: {old_package} → {new_package}")
        self.setMinimumSize(600, 450)

        layout = QVBoxLayout(self)

        guide_text = self._generate_guide()
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlainText(guide_text)
        layout.addWidget(self.text_area)

        button_layout = QHBoxLayout()

        self.preview_btn = QPushButton("Preview Changes")
        self.preview_btn.clicked.connect(self._on_preview_changes)
        button_layout.addWidget(self.preview_btn)

        self.auto_replace_btn = QPushButton("Auto-Replace Imports")
        self.auto_replace_btn.clicked.connect(self._on_auto_replace)
        button_layout.addWidget(self.auto_replace_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _generate_guide(self) -> str:
        from .core.migration_guide import generate_migration_summary
        return generate_migration_summary(self.old_package, self.new_package, self.project_path)

    def _on_auto_replace(self) -> None:
        from .core.migration_guide import auto_replace_usages

        reply = QMessageBox.question(
            self,
            "Confirm Replacement",
            "Apply changes to source files?\n\nA backup (.bak) will be created before modifying.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        count, files = auto_replace_usages(self.project_path, self.old_package, self.new_package)

        if count > 0:
            self.replacements_made = True
            self.text_area.append(f"\n\n✓ Successfully updated {count} file(s):")
            for f in files:
                self.text_area.append(f"  • {f}")
            self.auto_replace_btn.setEnabled(False)
            self.auto_replace_btn.setText("Imports Replaced")
        else:
            self.text_area.append("\n\nNo imports to replace.")

    def _on_preview_changes(self) -> None:
        from .core.migration_guide import preview_replacement

        previews = preview_replacement(self.project_path, self.old_package, self.new_package)

        if not previews:
            self.text_area.append("\n\nNo changes to preview.")
            return

        total_files = len(previews)
        total_changes = sum(len(p['changes']) for p in previews)
        self.text_area.append(f"\n\nPreview: {total_changes} change(s) in {total_files} file(s):\n")

        for preview in previews:
            self.text_area.append(f"--- {preview['file_path']} ---")
            for line in preview['diff']:
                if line.startswith('+') and not line.startswith('+++'):
                    self.text_area.append(f"  [ADD] {line.rstrip()}")
                elif line.startswith('-') and not line.startswith('---'):
                    self.text_area.append(f"  [DEL] {line.rstrip()}")
                elif line.startswith('@@'):
                    self.text_area.append(f"  {line.rstrip()}")
            self.text_area.append("")

    def was_replacement_made(self) -> bool:
        return self.replacements_made


class MainWindow(QMainWindow):
    def __init__(self, initial_project: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowTitle("LibFix - Python Dependency Analyzer")
        self.setGeometry(100, 100, 1100, 700)
        self.setMinimumSize(850, 550)

        self.project_directory: Optional[str] = None
        self.fetcher_thread: Optional[DependencyFetcherThread] = None
        self.replacement_thread: Optional[ReplacementThread] = None
        self.selected_item_data: Optional[tuple] = None
        self._dep_data: list[dict] = []

        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()

        if initial_project:
            self.project_directory = initial_project
            self.project_label.setText(f"Selected: {self.project_directory}")
            self.project_label.setStyleSheet("QLabel { color: #6a9955; font-size: 12px; padding: 2px 8px; }")
            QTimer.singleShot(100, self.find_and_parse_dependencies)
        self.python_interpreter_path = get_python_interpreter_path()
        self.dependencies_with_info: dict[str, Optional[dict]] = {}

        logger.info(f"LibFix started with Python: {self.python_interpreter_path}")

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setStyleSheet("QWidget { background: #2b2b2b; border-bottom: 1px solid #3c3c3c; }")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        self.select_button = QPushButton("  Select Project")
        self.select_button.setStyleSheet(self._btn_style("#5a9ead"))
        self.select_button.clicked.connect(self.select_project_directory)
        header_layout.addWidget(self.select_button)

        self.audit_button = QPushButton("  Audit Usage")
        self.audit_button.setStyleSheet(self._btn_style("#7b6896"))
        self.audit_button.clicked.connect(self.audit_dependencies)
        self.audit_button.setEnabled(False)
        header_layout.addWidget(self.audit_button)

        self.replace_button = QPushButton("  Replace Selected")
        self.replace_button.setStyleSheet(self._btn_style("#c07b5a"))
        self.replace_button.clicked.connect(self.replace_selected)
        self.replace_button.setEnabled(False)
        header_layout.addWidget(self.replace_button)

        header_layout.addStretch()

        self.project_label = QLabel("No project selected")
        self.project_label.setStyleSheet("QLabel { color: #888; font-size: 12px; padding: 2px 8px; }")
        header_layout.addWidget(self.project_label)

        main_layout.addWidget(header)

        # Content area with splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table area
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(8, 4, 8, 4)
        table_layout.setSpacing(4)

        # Stats row
        stats_row = QHBoxLayout()
        self.total_deps_label = QLabel("Dependencies: -")
        self.total_deps_label.setStyleSheet("QLabel { font-size: 13px; font-weight: bold; }")
        stats_row.addWidget(self.total_deps_label)

        self.inactive_deps_label = QLabel("Inactive: -")
        self.inactive_deps_label.setStyleSheet("QLabel { font-size: 13px; font-weight: bold; color: #e06c75; }")
        stats_row.addWidget(self.inactive_deps_label)
        stats_row.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setStyleSheet("QProgressBar { border-radius: 3px; } QProgressBar::chunk { background: #5a9ead; border-radius: 3px; }")
        stats_row.addWidget(self.progress_bar)
        stats_row.setStretchFactor(self.progress_bar, 1)

        table_layout.addLayout(stats_row)

        # Table
        self.dep_table = QTableWidget()
        self.dep_table.setColumnCount(4)
        self.dep_table.setHorizontalHeaderLabels(["Package", "Required", "Latest", "Status"])
        self.dep_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.dep_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.dep_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.dep_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.dep_table.horizontalHeader().resizeSection(1, 120)
        self.dep_table.horizontalHeader().resizeSection(2, 100)
        self.dep_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.dep_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.dep_table.setAlternatingRowColors(True)
        self.dep_table.verticalHeader().setVisible(False)
        self.dep_table.setStyleSheet(
            "QTableWidget { border: none; gridline-color: #333; } "
            "QTableWidget::item { padding: 4px; } "
            "QTableWidget::item:selected { background: #3a3a5a; } "
            "QHeaderView::section { background: #2b2b2b; padding: 6px; border: none; border-bottom: 2px solid #5a9ead; font-weight: bold; }"
        )
        self.dep_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.dep_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.dep_table.customContextMenuRequested.connect(self._on_table_context_menu)
        table_layout.addWidget(self.dep_table)

        splitter.addWidget(table_container)

        # Details panel
        details_header = QLabel("  Details")
        details_header.setStyleSheet(
            "QLabel { font-weight: bold; font-size: 12px; color: #aaa; padding: 4px 8px; "
            "border-bottom: 1px solid #444; }"
        )
        main_layout.addWidget(details_header)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setStyleSheet(
            "QTextEdit { border: none; background: transparent; font-size: 12px; padding: 4px 8px; }"
        )
        main_layout.addWidget(self.details_text)

        main_layout.addWidget(splitter)

        # Status bar at bottom
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("QLabel { color: #888; font-size: 11px; padding: 2px 8px; }")
        main_layout.addWidget(self.status_label)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setStyleSheet(
            "QToolBar { spacing: 4px; padding: 2px 8px; border-bottom: 1px solid #3c3c3c; } "
            "QToolButton { padding: 4px 8px; border-radius: 3px; } "
            "QToolButton:hover { background: #3a3a3a; }"
        )
        self.addToolBar(toolbar)

    def _setup_statusbar(self) -> None:
        self.statusBar().showMessage("Ready")
        self.statusBar().setStyleSheet("QStatusBar { border-top: 1px solid #3c3c3c; }")

    @staticmethod
    def _btn_style(color: str) -> str:
        return (
            f"QPushButton {{ background: {color}; color: #fff; border: none; padding: 6px 14px; "
            f"border-radius: 4px; font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {color}cc; }}"
            f"QPushButton:pressed {{ background: {color}99; }}"
            f"QPushButton:disabled {{ background: #444; color: #666; }}"
        )

    def closeEvent(self, a0) -> None:
        if self.fetcher_thread and self.fetcher_thread.isRunning():
            self.fetcher_thread.requestInterruption()
            if not self.fetcher_thread.wait(3000):
                self.fetcher_thread.terminate()
                self.fetcher_thread.wait()
        if self.replacement_thread and self.replacement_thread.isRunning():
            self.replacement_thread.requestInterruption()
            if not self.replacement_thread.wait(3000):
                self.replacement_thread.terminate()
                self.replacement_thread.wait()
        a0.accept()

    def select_project_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Python Project Directory")
        if directory:
            self.project_directory = directory
            self.project_label.setText(f"Selected: {self.project_directory}")
            self.project_label.setStyleSheet("QLabel { color: #6a9955; font-size: 12px; padding: 2px 8px; }")
            self.statusBar().showMessage(f"Project: {directory}")
            logger.info(f"Selected project: {self.project_directory}")
            self.find_and_parse_dependencies()

    def find_and_parse_dependencies(self) -> None:
        if self.project_directory:
            self.dep_table.setRowCount(0)
            self.status_label.setText("Scanning for dependency files...")
            self.total_deps_label.setText("Dependencies: -")
            self.inactive_deps_label.setText("Inactive: -")
            self.replace_button.setEnabled(False)
            self.selected_item_data = None

            dependency_files = find_dependency_files(self.project_directory)
            all_dependencies: set[str] = set()

            for files in dependency_files.values():
                for file_path in files:
                    deps = parse_all(file_path)
                    all_dependencies.update(deps)

            if all_dependencies:
                self.total_deps_label.setText(f"Dependencies: {len(all_dependencies)}")
                self.status_label.setText(f"Fetching info for {len(all_dependencies)} packages...")
                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(0)
                self.select_button.setEnabled(False)

                self.fetcher_thread = DependencyFetcherThread(list(all_dependencies))
                self.fetcher_thread.progress_signal.connect(self._on_progress)
                self.fetcher_thread.finished_signal.connect(self._on_deps_fetched)
                self.fetcher_thread.start()
            else:
                self.status_label.setText("No dependencies found")
                self.statusBar().showMessage("No dependencies found in this project.")

    def _on_progress(self, current: int, total: int) -> None:
        self.progress_bar.setValue(int((current / total) * 100))
        self.status_label.setText(f"Fetching package info... ({current}/{total})")

    def _on_deps_fetched(self, deps_with_info: dict[str, Optional[dict]]) -> None:
        self.dependencies_with_info = deps_with_info
        self.progress_bar.setVisible(False)
        self.select_button.setEnabled(True)
        self.audit_button.setEnabled(True)
        self._update_dependency_list_with_info()

    def _on_selection_changed(self) -> None:
        self.replace_button.setEnabled(False)
        self.selected_item_data = None
        selected = self.dep_table.selectedItems()
        if not selected:
            self.details_text.setPlainText("")
            return

        row = selected[0].row()
        if row < len(self._dep_data):
            entry = self._dep_data[row]
            dep = entry["dep"]
            alts = entry["alts"]
            inactive = entry["inactive"]
            reason = entry["reason"]
            version = entry["version"]

            if inactive and alts:
                self.selected_item_data = (dep, alts)
                self.replace_button.setEnabled(True)

            # Update details panel
            pkg_name = extract_package_name(dep)
            details = f"<b>{pkg_name}</b><br>"

            # Show learned category/ecosystem
            try:
                from .core.knowledge import get_knowledge_manager
                km = get_knowledge_manager()
                cat = km.get_category(pkg_name)
                eco = km.get_ecosystem(pkg_name)
                summary = km.get_summary(pkg_name)
                if cat and cat != "unknown":
                    details += f"Category: {cat}<br>"
                if eco and eco != "general":
                    details += f"Ecosystem: {eco}<br>"
                if summary:
                    details += f"<i>{summary}</i><br>"
            except Exception:
                pass

            details += f"Required: {entry['required'] or 'N/A'}<br>"
            details += f"Latest: {version}<br>"
            if inactive:
                details += f"<span style='color:#e06c75;'>Status: INACTIVE</span><br>"
                details += f"Reason: {reason}<br>"
                if alts:
                    details += f"<br><b>Alternatives:</b><br>"
                    for alt in alts:
                        details += f" &bull; {alt}<br>"
            elif entry.get("info"):
                details += f"<span style='color:#6a9955;'>Status: Active</span><br>"
            else:
                details += f"<span style='color:#e5c07b;'>Status: Unknown</span><br>"
            self.details_text.setHtml(details)

    def _on_table_context_menu(self, pos) -> None:
        row = self.dep_table.rowAt(pos.y())
        if row < 0:
            return
        if row >= len(self._dep_data):
            return
        entry = self._dep_data[row]
        pkg_name = extract_package_name(entry["dep"])

        menu = QMenu(self)
        copy_action = menu.addAction("Copy Package Name")
        menu.addSeparator()
        if entry["inactive"]:
            acknowledge_action = menu.addAction("Acknowledge (ignore this warning)")
        else:
            acknowledge_action = None

        action = menu.exec(self.dep_table.mapToGlobal(pos))
        if action == copy_action:
            QApplication.clipboard().setText(pkg_name)
        elif acknowledge_action and action == acknowledge_action and self.project_directory:
            history_manager = load_audit_history(self.project_directory)
            history_manager.acknowledge(pkg_name, "inactive", "")
            self.find_and_parse_dependencies()

    def _dep_table_item_text(self, row: int) -> str:
        item = self.dep_table.item(row, 0)
        if item:
            return item.text()
        return ""

    def _get_inactive_deps(self) -> dict[str, tuple[bool, list[str]]]:
        inactive_deps: dict[str, tuple[bool, list[str]]] = {}
        for dep, info in self.dependencies_with_info.items():
            package_name = extract_package_name(dep)
            if info and 'info' in info:
                inactive, _, alts = is_potentially_inactive(info, package_name)
                if inactive:
                    inactive_deps[dep] = (inactive, alts)
        return inactive_deps

    def audit_dependencies(self) -> None:
        if not self.project_directory or not self.dependencies_with_info:
            QMessageBox.warning(self, "No Project", "Please select a project first.")
            return

        deps = list(self.dependencies_with_info.keys())
        dialog = AuditDialog(self, self.project_directory, deps)
        dialog.exec()

    def _is_dep_handled(self, history_manager, pkg_name: str) -> bool:
        """Check if a dep has been resolved or acknowledged under any issue type."""
        normalized = pkg_name.lower().replace("-", "_")
        for entry in history_manager.history.resolved:
            if entry["package_name"].lower().replace("-", "_") == normalized:
                return True
        for entry in history_manager.history.acknowledged:
            if entry["package_name"].lower().replace("-", "_") == normalized:
                return True
        return False

    def _update_dependency_list_with_info(self) -> None:
        self.dep_table.setRowCount(0)
        self._dep_data.clear()
        inactive_count = 0

        for dep, info in self.dependencies_with_info.items():
            latest_version = "N/A"
            required_version = ""
            inactive = False
            reason = ""
            alternatives: list[str] = []

            package_name = extract_package_name(dep)

            if info and 'info' in info and 'version' in info['info']:
                latest_version = info['info']['version']
                inactive, reason, alternatives = is_potentially_inactive(info, package_name)

            # Extract required version from dep string
            for op in ['>=', '<=', '==', '!=', '~=', '>', '<']:
                if op in dep:
                    required_version = dep.split(op)[-1].strip().rstrip(']').rstrip("'").rstrip('"')
                    break

            if inactive:
                inactive_count += 1

            self._dep_data.append({
                "dep": dep,
                "required": required_version,
                "version": latest_version,
                "inactive": inactive,
                "reason": reason,
                "alts": alternatives,
                "info": info,
            })

        # Sort: inactive first, then alphabetically
        self._dep_data.sort(key=lambda x: (not x["inactive"], x["dep"].lower()))

        for i, entry in enumerate(self._dep_data):
            self.dep_table.insertRow(i)
            # Package column (clean name)
            pkg_name = extract_package_name(entry["dep"])
            self.dep_table.setItem(i, 0, QTableWidgetItem(pkg_name))
            self.dep_table.setItem(i, 1, QTableWidgetItem(entry["required"]))
            self.dep_table.setItem(i, 2, QTableWidgetItem(entry["version"]))

            # Status column
            if entry["inactive"]:
                status_item = QTableWidgetItem("INACTIVE")
                status_item.setForeground(QColor("#e06c75"))
                font = status_item.font()
                font.setBold(True)
                status_item.setFont(font)
            elif entry.get("info"):
                status_item = QTableWidgetItem("Active")
                status_item.setForeground(QColor("#6a9955"))
            else:
                status_item = QTableWidgetItem("Unknown")
                status_item.setForeground(QColor("#e5c07b"))
            self.dep_table.setItem(i, 3, status_item)

        # Auto-acknowledge inactive deps and clean up stale acknowledgments
        if self.project_directory:
            history_manager = load_audit_history(self.project_directory)
            history_manager.load()

            # Collect currently inactive package names
            currently_inactive = {
                extract_package_name(entry["dep"]).lower().replace("-", "_")
                for entry in self._dep_data if entry["inactive"]
            }

            # Remove acknowledgments for deps that are no longer inactive
            # (e.g. got a new release, or removed from project)
            history_manager.history.acknowledged = [
                ack for ack in history_manager.history.acknowledged
                if ack["package_name"].lower().replace("-", "_") in currently_inactive
            ]

            # Auto-acknowledge all currently inactive deps for next time
            for entry in self._dep_data:
                if entry["inactive"]:
                    pkg = extract_package_name(entry["dep"])
                    history_manager.acknowledge(pkg, "inactive", "auto-acknowledged on scan")

            history_manager.save()

            # Filter: only show inactive deps that are new (not previously acknowledged)
            has_prior_acknowledgments = any(
                ack.get("issue_type") == "inactive"
                for ack in history_manager.history.acknowledged
            )
            if has_prior_acknowledgments:
                self._dep_data = [
                    entry for entry in self._dep_data
                    if not self._is_dep_handled(history_manager, extract_package_name(entry["dep"]))
                ]
                inactive_count = sum(1 for e in self._dep_data if e["inactive"])

        # Learn co-occurrence patterns from this project's packages
        if self.dependencies_with_info and self.project_directory:
            all_pkgs = [extract_package_name(d) for d in self.dependencies_with_info]
            try:
                from .core.knowledge import record_project_packages
                record_project_packages(all_pkgs)
            except Exception:
                pass

        self.total_deps_label.setText(f"Dependencies: {len(self._dep_data)}")
        self.inactive_deps_label.setText(f"Inactive: {inactive_count}")
        self.status_label.setText("Analysis complete" if self.dependencies_with_info else "")
        self.statusBar().showMessage(
            f"Analysis complete — {len(self._dep_data)} packages, {inactive_count} inactive"
        )

    def replace_selected(self) -> None:
        if not self.selected_item_data or not self.project_directory:
            return

        old_dep, alternatives = self.selected_item_data

        if not alternatives:
            QMessageBox.warning(self, "No Alternatives", "No alternative packages available for this dependency.")
            return

        dialog = AlternativeSelectionDialog(self, old_dep, alternatives)
        new_dep = dialog.get_selected()

        if not new_dep:
            return

        self._selected_replacement = new_dep
        self.status_label.setText(f"Replacing {old_dep} with {new_dep}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.select_button.setEnabled(False)
        self.replace_button.setEnabled(False)

        self.replacement_thread = ReplacementThread(self.project_directory, old_dep, new_dep)
        self.replacement_thread.progress_signal.connect(self._on_replacement_progress)
        self.replacement_thread.finished_signal.connect(self._on_replacement_finished)
        self.replacement_thread.start()

    def _on_replacement_progress(self, message: str, success: bool) -> None:
        prefix = "✓ " if success else "✗ "
        self.status_label.setText(prefix + message)

    def _on_replacement_finished(self) -> None:
        self.progress_bar.setVisible(False)
        self.select_button.setEnabled(True)

        selected_new = getattr(self, '_selected_replacement', None)
        old_dep = self.selected_item_data[0] if self.selected_item_data else ""

        # Mark the replaced dep as resolved in history
        if old_dep and self.project_directory:
            old_name = extract_package_name(old_dep)
            history_manager = load_audit_history(self.project_directory)
            action = f"replaced_with_{extract_package_name(selected_new)}" if selected_new else "replaced"
            history_manager.mark_resolved(old_name, "inactive", action, [])

        should_rescan = False

        if selected_new and old_dep and self.project_directory:
            old_name = extract_package_name(old_dep)
            try:
                guide_dialog = MigrationGuideDialog(
                    self, old_name, selected_new, self.project_directory
                )
                guide_dialog.exec()
                if guide_dialog.was_replacement_made():
                    should_rescan = True
            except Exception as e:
                logger.error(f"Error showing migration guide: {e}")
            reply = QMessageBox.question(
                self,
                "Imports Updated",
                "Imports were updated. Would you like to re-scan the project to verify the changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.find_and_parse_dependencies()
            else:
                self.status_label.setText("")
        else:
            reply = QMessageBox.question(
                self,
                "Replacement Complete",
                "Would you like to re-scan the project to verify the changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.find_and_parse_dependencies()
            else:
                self.status_label.setText("")


def main(initial_project: Optional[str] = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='PyQt6'))
    window = MainWindow(initial_project=initial_project)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
