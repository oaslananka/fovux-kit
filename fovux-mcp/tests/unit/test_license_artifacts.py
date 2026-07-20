"""Tests for canonical Apache-2.0 distribution artifacts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_license_boundaries.py"
SBOM_SCRIPT_PATH = REPO_ROOT / "scripts" / "build_spdx_sbom.py"
CANONICAL_APACHE_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_license_boundaries", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_common_fixture(root: Path) -> None:
    (root / "docs").mkdir(parents=True)
    (root / "fovux-mcp" / "src" / "fovux" / "core").mkdir(parents=True)
    (root / "fovux-mcp" / "src" / "fovux" / "tools").mkdir(parents=True)
    (root / "fovux-mcp-npm").mkdir(parents=True)
    (root / "fovux-studio").mkdir(parents=True)

    (root / "docs" / "licensing-boundaries.md").write_text(
        "Apache-2.0 Ultralytics ONNX TensorRT CoreML OpenVINO TFLite NCNN RKNN "
        "W&B Hugging Face no-telemetry\n",
        encoding="utf-8",
    )
    (root / "fovux-mcp" / "src" / "fovux" / "core" / "doctor.py").write_text(
        "Ultralytics AGPL NOTICE\n",
        encoding="utf-8",
    )
    (root / "fovux-mcp" / "src" / "fovux" / "tools" / "bundles.py").write_text(
        "package_versions Ultralytics\n",
        encoding="utf-8",
    )


def test_checker_rejects_modified_license_and_missing_package_artifacts(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _write_common_fixture(tmp_path)

    for relative in ("LICENSE", "fovux-mcp/LICENSE", "fovux-studio/LICENSE"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("modified license text\n", encoding="utf-8")
    for relative in ("NOTICE", "fovux-mcp/NOTICE"):
        (tmp_path / relative).write_text("Fovux notice\n", encoding="utf-8")

    (tmp_path / "fovux-mcp" / "pyproject.toml").write_text(
        '[project]\nlicense = { file = "LICENSE" }\n',
        encoding="utf-8",
    )
    (tmp_path / "fovux-mcp-npm" / "package.json").write_text(
        json.dumps({"license": "Apache-2.0", "files": ["bin/"]}),
        encoding="utf-8",
    )
    (tmp_path / "fovux-studio" / "package.json").write_text(
        json.dumps({"license": "Apache-2.0"}),
        encoding="utf-8",
    )

    module.ROOT = tmp_path

    assert module.main() == 1


def test_repository_license_artifacts_are_canonical() -> None:
    module = _load_module()

    assert module.main() == 0
    assert module.CANONICAL_APACHE_SHA256 == CANONICAL_APACHE_SHA256


def test_spdx_builder_prefers_pep639_license_expression() -> None:
    spec = importlib.util.spec_from_file_location("build_spdx_sbom", SBOM_SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Metadata(dict[str, str]):
        def get_all(self, _name: str) -> list[str]:
            return []

    class Distribution:
        metadata = Metadata({"License-Expression": "Apache-2.0"})

    assert module._license_for(Distribution()) == "Apache-2.0"
