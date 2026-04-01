import logging
import os
import sys
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, Qt
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
)
import qdarkstyle

from .core.dependency_finder import find_dependency_files
from .utils.path_utils import get_python_interpreter_path
from .core.dependency_parser import parse_all
from .core.pypi_utils import get_package_info_from_pypi
from .core.dependency_analyzer import is_potentially_inactive
from .core.dependency_replacer import replace_dependency

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
            package_name = self._extract_package_name(dep)
            info = get_package_info_from_pypi(package_name)
            deps_with_info[dep] = info
            self.progress_signal.emit(i + 1, total)
        self.finished_signal.emit(deps_with_info)

    @staticmethod
    def _extract_package_name(dependency_string: str) -> str:
        parts = dependency_string.split('>', 1)[0].split('<', 1)[0].split('=', 1)[0].split('!', 1)[0]
        return parts.strip()


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
                self.add_missing_btn.setEnabled(False)
            else:
                self.text_area.append("\n\nNo requirements.txt found. Cannot add dependencies.")

    def _integrate_all(self) -> None:
        from .core.dependency_integrator import integrate_missing_dependencies

        if not self.audit_result or not self.audit_result.missing_dependencies:
            return

        missing = self.audit_result.missing_dependencies

        reply = QMessageBox.question(
            self,
            "Full Integration",
            f"This will:\n1. Install {len(missing)} packages via pip\n2. Add import statements to source files\n3. Add to requirements.txt\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.text_area.append("\n\nIntegrating dependencies...")

            results = integrate_missing_dependencies(
                self.project_path,
                missing,
                install=True
            )

            success_count = sum(1 for r in results if r.success)
            self.text_area.append(f"\n\nIntegration complete: {success_count}/{len(results)} successful")

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

            self.add_missing_btn.setEnabled(False)
            self.integrate_btn.setEnabled(False)


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

    def was_replacement_made(self) -> bool:
        return self.replacements_made


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LibFix - Python Dependency Analyzer")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header_layout = QHBoxLayout()
        self.select_button = QPushButton("Select Python Project")
        self.select_button.clicked.connect(self.select_project_directory)
        header_layout.addWidget(self.select_button)

        self.audit_button = QPushButton("Audit Usage")
        self.audit_button.clicked.connect(self.audit_dependencies)
        self.audit_button.setEnabled(False)
        header_layout.addWidget(self.audit_button)

        self.replace_button = QPushButton("Replace Selected")
        self.replace_button.clicked.connect(self.replace_selected)
        self.replace_button.setEnabled(False)
        header_layout.addWidget(self.replace_button)
        self.layout.addLayout(header_layout)

        self.project_label = QLabel("No project selected")
        self.project_label.setStyleSheet("QLabel { font-size: 14px; color: #888; margin-top: 10px; }")
        self.project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.project_label)

        self.stats_layout = QHBoxLayout()
        self.total_deps_label = QLabel("Dependencies: -")
        self.inactive_deps_label = QLabel("Inactive: -")
        self.stats_layout.addWidget(self.total_deps_label)
        self.stats_layout.addStretch()
        self.stats_layout.addWidget(self.inactive_deps_label)
        self.layout.addLayout(self.stats_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("QLabel { color: #888; font-size: 12px; }")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)

        self.dependency_list_widget = QListWidget()
        self.dependency_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.dependency_list_widget.itemClicked.connect(self.on_item_clicked)
        self.layout.addWidget(self.dependency_list_widget)

        self.central_widget.setLayout(self.layout)

        self.project_directory: Optional[str] = None
        self.python_interpreter_path = get_python_interpreter_path()
        self.dependencies_with_info: dict[str, Optional[dict]] = {}
        self.fetcher_thread: Optional[DependencyFetcherThread] = None
        self.replacement_thread: Optional[ReplacementThread] = None
        self.selected_item_data: Optional[tuple] = None

        logger.info(f"LibFix started with Python: {self.python_interpreter_path}")

    def select_project_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Python Project Directory")
        if directory:
            self.project_directory = directory
            self.project_label.setText(f"Selected: {self.project_directory}")
            logger.info(f"Selected project: {self.project_directory}")
            self.find_and_parse_dependencies()

    def find_and_parse_dependencies(self) -> None:
        if self.project_directory:
            self.dependency_list_widget.clear()
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
                self.dependency_list_widget.addItem("No dependencies found in this project.")

    def _on_progress(self, current: int, total: int) -> None:
        self.progress_bar.setValue(int((current / total) * 100))
        self.status_label.setText(f"Fetching package info... ({current}/{total})")

    def _on_deps_fetched(self, deps_with_info: dict[str, Optional[dict]]) -> None:
        self.dependencies_with_info = deps_with_info
        self.progress_bar.setVisible(False)
        self.select_button.setEnabled(True)
        self.audit_button.setEnabled(True)
        self._update_dependency_list_with_info()

    def on_item_clicked(self, item: QListWidget.item) -> None:
        self.replace_button.setEnabled(False)
        self.selected_item_data = None

        for dep, (inactive, alts) in self._get_inactive_deps().items():
            if dep in item.text() and alts:
                self.selected_item_data = (dep, alts)
                self.replace_button.setEnabled(True)
                break

    def _get_inactive_deps(self) -> dict[str, tuple[bool, list[str]]]:
        inactive_deps: dict[str, tuple[bool, list[str]]] = {}
        for dep, info in self.dependencies_with_info.items():
            package_name = self._extract_package_name(dep)
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

    def _update_dependency_list_with_info(self) -> None:
        self.dependency_list_widget.clear()
        inactive_count = 0
        inactive_items = []
        active_items = []

        for dep, info in self.dependencies_with_info.items():
            latest_version = "N/A"
            inactive = False
            reason = ""
            alternatives: list[str] = []

            package_name = self._extract_package_name(dep)

            if info and 'info' in info and 'version' in info['info']:
                latest_version = info['info']['version']
                inactive, reason, alternatives = is_potentially_inactive(info, package_name)

            item_text = f"{dep} (Latest: {latest_version})"
            if inactive:
                inactive_count += 1
                item_text += " [INACTIVE]"
                if reason:
                    item_text += f" - {reason}"
                if alternatives:
                    item_text += f" (Try: {', '.join(alternatives)})"
                inactive_items.append((item_text, dep, alternatives))
            elif info:
                active_items.append((item_text, dep, []))

        inactive_items.sort(key=lambda x: x[0])
        active_items.sort(key=lambda x: x[0])

        for item_text, _, _ in inactive_items + active_items:
            self.dependency_list_widget.addItem(item_text)

        self.inactive_deps_label.setText(f"Inactive: {inactive_count}")
        self.status_label.setText("Analysis complete" if self.dependencies_with_info else "")

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
        self.status_label.setText(message)
        prefix = "✓ " if success else "✗ "
        self.status_label.setText(prefix + message)

    def _on_replacement_finished(self) -> None:
        self.progress_bar.setVisible(False)
        self.select_button.setEnabled(True)

        selected_new = getattr(self, '_selected_replacement', None)
        old_dep = self.selected_item_data[0] if self.selected_item_data else ""

        should_rescan = False

        if selected_new and old_dep and self.project_directory:
            old_name = self._extract_package_name(old_dep)
            try:
                guide_dialog = MigrationGuideDialog(
                    self, old_name, selected_new, self.project_directory
                )
                guide_dialog.exec()
                if guide_dialog.was_replacement_made():
                    should_rescan = True
            except Exception as e:
                logger.error(f"Error showing migration guide: {e}")

        if should_rescan:
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

    def _extract_package_name(self, dependency_string: str) -> str:
        parts = dependency_string.split('>', 1)[0].split('<', 1)[0].split('=', 1)[0].split('!', 1)[0]
        return parts.strip()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='PyQt6'))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
