import pytest
import os
import tempfile
from src.core.audit_history import (
    AuditHistoryManager,
    load_audit_history,
)


class TestAuditHistory:
    def test_creates_history_file(self):
        temp_dir = tempfile.mkdtemp()
        manager = AuditHistoryManager(temp_dir)

        assert not os.path.exists(manager.history_file)

        manager.record_audit()
        manager.save()

        assert os.path.exists(manager.history_file)

        import shutil
        shutil.rmtree(temp_dir)

    def test_records_audit(self):
        temp_dir = tempfile.mkdtemp()
        manager = AuditHistoryManager(temp_dir)

        manager.record_audit()
        manager.record_audit()
        manager.save()

        history = manager.load()
        assert history.total_audits == 2

        import shutil
        shutil.rmtree(temp_dir)

    def test_marks_resolved(self):
        temp_dir = tempfile.mkdtemp()
        manager = AuditHistoryManager(temp_dir)

        assert not manager.is_resolved("requests", "unused")

        manager.mark_resolved("requests", "unused", "removed")

        assert manager.is_resolved("requests", "unused")
        assert not manager.is_resolved("flask", "unused")

        import shutil
        shutil.rmtree(temp_dir)

    def test_acknowledges_issue(self):
        temp_dir = tempfile.mkdtemp()
        manager = AuditHistoryManager(temp_dir)

        assert not manager.is_acknowledged("requests", "missing")

        manager.acknowledge("requests", "missing", "already installed")

        assert manager.is_acknowledged("requests", "missing")

        import shutil
        shutil.rmtree(temp_dir)

    def test_filters_resolved_from_audit(self):
        temp_dir = tempfile.mkdtemp()
        req_file = os.path.join(temp_dir, "requirements.txt")
        with open(req_file, "w") as f:
            f.write("requests\nflask\n")

        manager = AuditHistoryManager(temp_dir)
        manager.mark_resolved("flask", "unused", "removed")

        issues = [("requests", "unused"), ("flask", "unused"), ("numpy", "unused")]
        filtered, skipped = manager.filter_unused_by_history(issues)

        assert ("requests", "unused") in filtered
        assert ("flask", "unused") in skipped
        assert ("numpy", "unused") in filtered

        import shutil
        os.unlink(req_file)
        shutil.rmtree(temp_dir)

    def test_loads_existing_history(self):
        temp_dir = tempfile.mkdtemp()
        manager1 = AuditHistoryManager(temp_dir)
        manager1.record_audit()
        manager1.mark_resolved("flask", "unused", "removed")
        manager1.save()

        manager2 = AuditHistoryManager(temp_dir)
        history = manager2.load()

        assert history.total_audits == 1
        assert manager2.is_resolved("flask", "unused")

        import shutil
        shutil.rmtree(temp_dir)

    def test_clears_history(self):
        temp_dir = tempfile.mkdtemp()
        manager = AuditHistoryManager(temp_dir)
        manager.record_audit()
        manager.mark_resolved("flask", "unused", "removed")
        manager.save()

        assert os.path.exists(manager.history_file)

        manager.clear_history()
        history = manager.load()

        assert history.total_audits == 0
        assert not manager.is_resolved("flask", "unused")

        import shutil
        shutil.rmtree(temp_dir)
