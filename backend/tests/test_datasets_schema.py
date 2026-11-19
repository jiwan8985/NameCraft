"""Phase 0 산출 데이터셋의 구조 검증. 계산 로직 검증은 Phase 3·4에서 동일 파일을 재사용한다."""

from __future__ import annotations

import json

import pytest
import yaml

pytestmark = pytest.mark.golden

GOLDEN_STATUSES = {"definitional", "formula_derived", "externally_verified", "pending"}
MANIFEST_FIELDS = {"id", "name", "url", "authority", "purpose", "access_method", "license",
                   "license_verified_at", "terms_url", "retrieved_at", "effective_date",
                   "checksum_sha256", "coverage", "status", "notes"}
MANIFEST_STATUSES = {"candidate", "license_review", "approved", "ingested", "rejected"}


def _golden_files(repo_root):
    return sorted((repo_root / "datasets" / "golden-tests").glob("*.yaml"))


def test_golden_files_exist(repo_root):
    assert {p.name for p in _golden_files(repo_root)} >= {"saju.yaml", "numerology.yaml"}


def test_golden_cases_well_formed(repo_root):
    for path in _golden_files(repo_root):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert doc["schema_version"] == 1 and doc["profile_id"]
        ids = [c["id"] for c in doc["cases"]]
        assert len(ids) == len(set(ids)), f"duplicate ids in {path.name}"
        for c in doc["cases"]:
            assert c["status"] in GOLDEN_STATUSES, c["id"]
            # pending 이 아닌 케이스는 반드시 구체적 기대값을 가진다
            assert (c["expected"] == "pending") == (c["status"] == "pending"), c["id"]


def test_source_manifests_complete(repo_root):
    files = list((repo_root / "datasets" / "source-manifests").glob("*.yaml"))
    assert len(files) >= 10
    for f in files:
        m = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert MANIFEST_FIELDS <= m.keys(), f.name
        assert m["id"] == f.stem and m["status"] in MANIFEST_STATUSES
        if m["status"] in {"approved", "ingested"}:  # 라이선스 확인 없이 승인 금지
            assert m["license"] and m["license_verified_at"], f.name


def test_demo_usage_fixture_is_flagged(repo_root):
    doc = json.loads((repo_root / "datasets" / "fixtures" / "ai-usage-demo.json").read_text(encoding="utf-8"))
    assert doc["is_demo"] is True
    for table in ("ai_sessions", "ai_usage_events", "ai_quota_windows"):
        assert doc[table] and all(r["is_demo"] is True and r["source_kind"] == "demo" for r in doc[table])
