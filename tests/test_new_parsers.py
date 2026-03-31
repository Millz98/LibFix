import pytest
import tempfile
import os
from src.core.dependency_parser import (
    parse_requirements_txt,
    parse_setup_py,
    parse_setup_cfg,
    parse_pyproject_toml,
    parse_pipfile,
    parse_all,
)


class TestSetupCfgParser:
    def test_parses_simple_deps(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as f:
            f.write("""[metadata]
name = test-project

[options]
install_requires =
    requests>=2.28
    flask>=2.0
""")
            temp_path = f.name

        try:
            deps = parse_setup_cfg(temp_path)
            assert len(deps) == 2
            assert any("requests" in d for d in deps)
        finally:
            os.unlink(temp_path)


class TestPipfileParser:
    def test_parses_packages(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='', delete=False) as f:
            f.write("""[packages]
requests = "*"
flask = "^2.0"
django = {version = "==4.0.0"}
""")
            temp_path = f.name

        try:
            deps = parse_pipfile(temp_path)
            assert len(deps) == 3
            assert "requests" in deps
            assert any("flask" in d for d in deps)
        finally:
            os.unlink(temp_path)


class TestParseAll:
    def test_auto_detects_requirements(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("requests\nflask\n")
            temp_path = f.name

        try:
            deps = parse_all(temp_path)
            assert len(deps) == 2
        finally:
            os.unlink(temp_path)

    def test_auto_detects_setup_cfg(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as f:
            f.write("[options]\ninstall_requires = requests\n")
            temp_path = f.name

        try:
            deps = parse_all(temp_path)
            assert "requests" in deps
        finally:
            os.unlink(temp_path)
