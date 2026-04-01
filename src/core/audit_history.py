import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ResolvedIssue:
    package_name: str
    issue_type: str
    resolved_at: str
    action: str
    files_affected: list[str] = field(default_factory=list)


@dataclass
class AcknowledgedIssue:
    package_name: str
    issue_type: str
    acknowledged_at: str
    reason: str = ""


@dataclass
class AuditHistory:
    project_path: str
    first_audit: str
    last_audit: str
    total_audits: int
    resolved: list[dict] = field(default_factory=list)
    acknowledged: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "first_audit": self.first_audit,
            "last_audit": self.last_audit,
            "total_audits": self.total_audits,
            "resolved": self.resolved,
            "acknowledged": self.acknowledged,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditHistory":
        return cls(
            project_path=data.get("project_path", ""),
            first_audit=data.get("first_audit", ""),
            last_audit=data.get("last_audit", ""),
            total_audits=data.get("total_audits", 0),
            resolved=data.get("resolved", []),
            acknowledged=data.get("acknowledged", []),
        )


class AuditHistoryManager:
    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        self.libfix_dir = os.path.join(self.project_path, ".libfix")
        self.history_file = os.path.join(self.libfix_dir, "audit-history.json")
        self.history: Optional[AuditHistory] = None

    def _ensure_dir(self) -> None:
        if not os.path.exists(self.libfix_dir):
            os.makedirs(self.libfix_dir)

    def load(self) -> AuditHistory:
        if self.history is not None:
            return self.history

        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.history = AuditHistory.from_dict(data)
                logger.debug(f"Loaded audit history from {self.history_file}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load audit history: {e}")
                self.history = self._create_new()
        else:
            self.history = self._create_new()

        return self.history

    def _create_new(self) -> AuditHistory:
        return AuditHistory(
            project_path=self.project_path,
            first_audit=datetime.now().isoformat(),
            last_audit=datetime.now().isoformat(),
            total_audits=0,
            resolved=[],
            acknowledged=[],
        )

    def save(self) -> None:
        if self.history is None:
            return

        self._ensure_dir()
        self.history.last_audit = datetime.now().isoformat()

        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history.to_dict(), f, indent=2)
            logger.debug(f"Saved audit history to {self.history_file}")
        except IOError as e:
            logger.error(f"Could not save audit history: {e}")

    def record_audit(self) -> None:
        history = self.load()
        history.total_audits += 1
        self.save()

    def is_acknowledged(self, package_name: str, issue_type: str) -> bool:
        history = self.load()
        normalized = package_name.lower().replace("-", "_")

        for ack in history.acknowledged:
            ack_name = ack["package_name"].lower().replace("-", "_")
            if ack_name == normalized and ack["issue_type"] == issue_type:
                return True
        return False

    def acknowledge(self, package_name: str, issue_type: str, reason: str = "") -> None:
        if self.is_acknowledged(package_name, issue_type):
            return

        history = self.load()
        history.acknowledged.append({
            "package_name": package_name,
            "issue_type": issue_type,
            "acknowledged_at": datetime.now().isoformat(),
            "reason": reason,
        })
        self.save()

    def is_resolved(self, package_name: str, issue_type: str) -> bool:
        history = self.load()
        normalized = package_name.lower().replace("-", "_")

        for res in history.resolved:
            res_name = res["package_name"].lower().replace("-", "_")
            if res_name == normalized and res["issue_type"] == issue_type:
                return True
        return False

    def mark_resolved(
        self,
        package_name: str,
        issue_type: str,
        action: str,
        files_affected: list[str] = None
    ) -> None:
        if self.is_resolved(package_name, issue_type):
            return

        history = self.load()
        history.resolved.append({
            "package_name": package_name,
            "issue_type": issue_type,
            "resolved_at": datetime.now().isoformat(),
            "action": action,
            "files_affected": files_affected or [],
        })
        self.save()

    def filter_unused_by_history(
        self,
        unused_dependencies: list[tuple[str, str]]
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """Filter out resolved/acknowledged issues.

        Returns:
            Tuple of (filtered_issues, skipped_issues)
        """
        history = self.load()
        filtered = []
        skipped = []

        for pkg, issue_type in unused_dependencies:
            if self.is_resolved(pkg, issue_type) or self.is_acknowledged(pkg, issue_type):
                skipped.append((pkg, issue_type))
            else:
                filtered.append((pkg, issue_type))

        return filtered, skipped

    def get_summary(self) -> dict:
        history = self.load()
        return {
            "total_audits": history.total_audits,
            "total_resolved": len(history.resolved),
            "total_acknowledged": len(history.acknowledged),
            "first_audit": history.first_audit,
            "last_audit": history.last_audit,
        }

    def clear_history(self) -> None:
        self.history = self._create_new()
        if os.path.exists(self.history_file):
            os.remove(self.history_file)
        logger.info(f"Cleared audit history for {self.project_path}")


def load_audit_history(project_path: str) -> AuditHistoryManager:
    return AuditHistoryManager(project_path)


if __name__ == "__main__":
    import tempfile

    logging.basicConfig(level=logging.DEBUG)

    temp_dir = tempfile.mkdtemp()
    manager = AuditHistoryManager(temp_dir)

    manager.record_audit()
    manager.mark_resolved("requests", "unused", "removed from requirements.txt")
    manager.acknowledge("flask", "inactive", "will upgrade later")

    history = manager.load()
    print(json.dumps(history.to_dict(), indent=2))

    manager.clear_history()
    os.rmdir(temp_dir)
