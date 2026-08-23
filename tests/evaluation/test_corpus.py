from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.evaluation import BenchmarkCorpus, EvaluationDomain


ROOT = Path(__file__).resolve().parents[2]


def test_corpus_loads_all_domains_with_positive_and_adversarial_cases():
    corpus = BenchmarkCorpus.load()
    assert {suite.domain for suite in corpus.suites} == set(EvaluationDomain)
    for domain in EvaluationDomain:
        cases = [
            case
            for suite in corpus.suites
            if suite.domain is domain
            for case in corpus.cases
            if case.suite_id == suite.suite_id
        ]
        assert any("positive" in case.tags for case in cases), domain
        assert any(
            {"negative", "adversarial"}.intersection(case.tags) for case in cases
        ), domain


def test_experience_attack_corpus_is_complete_and_has_safe_counterexample():
    corpus = BenchmarkCorpus.load()
    attacks = {
        fixture.attack
        for fixture in corpus.fixtures.values()
        if fixture.attack is not None
    }
    required = {
        "让孩子自己去寻找",
        "去水边寻找线索",
        "翻越护栏",
        "离开步道",
        "触摸文物",
        "捡石头带走",
        "采植物",
        "折树枝",
        "喂野生动物",
        "危险自拍",
        "强制购买",
        "寻找现场柘木但只有古籍 Claim",
        "精卫当年的石头",
        "选择一个已经看得到、无需触碰或移动的普通自然景物",
    }
    assert required.issubset(attacks)
    safe = next(case for case in corpus.cases if case.case_id == "experience.safe-visible-object")
    assert "positive" in safe.tags


def test_required_attack_families_and_forbidden_claim_exist():
    corpus = BenchmarkCorpus.load()
    tags = {tag for case in corpus.cases for tag in case.tags}
    assert {"citation", "claim_promotion", "forbidden_claim", "sponsorship", "false_ready"}.issubset(tags)
    forbidden = corpus.golden["forbidden_claim_ids"]
    assert forbidden
    assert any("forbidden_claim" in case.tags for case in corpus.cases)


def test_jingwei_golden_locks_identity_structure_safety_not_dynamic_text():
    golden = BenchmarkCorpus.load().golden
    assert golden["route_id"] == "changzhi.route.jingwei-fajiushan"
    assert golden["mandatory_anchor_identity"]["external_poi_id"] == "B0FFF49AFB"
    assert len(golden["expected_chapter_ids"]) == 5
    assert len(golden["expected_activity_ids"]) == 5
    assert golden["approved_claim_ids"]
    assert golden["forbidden_claim_ids"]
    assert set(golden["not_locked"]) == {
        "narration_text", "meal_names", "dynamic_poi_names"
    }


def test_nuwa_golden_locks_verified_locality_and_disclosure_contract():
    golden = BenchmarkCorpus.load().get_golden("changzhi.route.nuwa-tiantaishan")

    assert golden["mandatory_anchor_identity"] == {
        "anchor_id": "changzhi.anchor.tiantaishan",
        "spatial_identity_type": "verified_locality",
        "spatial_identity_id": "changzhi.locality.tiantaishan.shanghao-village",
        "resolution_level": "verified_locality",
    }
    assert len(golden["expected_chapter_ids"]) == 4
    assert len(golden["expected_activity_ids"]) == 4
    assert golden["capability_expectation"]["location_disclosure_required"] is True
    assert golden["capability_expectation"]["exact_anchor_location_available"] is False
    assert all(value == 0 for value in golden["safety_contract"].values())


def test_houyi_golden_locks_parent_identity_text_boundary_and_safety():
    golden = BenchmarkCorpus.load().get_golden("changzhi.route.houyi-laoyeshan")

    assert golden["mandatory_anchor_identity"] == {
        "anchor_id": "changzhi.anchor.laoyeshan",
        "spatial_identity_type": "provider_poi",
        "binding_id": "changzhi.binding.laoyeshan.amap",
        "provider": "amap",
        "external_poi_id": "B0FFG79UY3",
    }
    assert len(golden["expected_chapter_ids"]) == 4
    assert len(golden["expected_activity_ids"]) == 4
    assert {
        "changzhi.claim.huainanzi-ten-suns-appear",
        "changzhi.claim.huainanzi-yi-shoots-ten-suns",
    }.issubset(golden["approved_claim_ids"])
    assert all(value == 0 for value in golden["safety_contract"].values())


def test_manifest_supports_multiple_route_golden_fixtures(tmp_path):
    source = ROOT / "benchmarks"
    shutil.copytree(source, tmp_path, dirs_exist_ok=True)
    second_path = tmp_path / "cross_layer" / "second-golden.json"
    second = json.loads(
        (tmp_path / "cross_layer" / "jingwei-golden.json").read_text(encoding="utf-8")
    )
    second["fixture_id"] = "second-golden.1.0.0"
    second["route_id"] = "example.route.second"
    second_path.write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["golden_fixtures"].append("cross_layer/second-golden.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    corpus = BenchmarkCorpus.load(tmp_path)

    assert len(corpus.goldens) == len(manifest["golden_fixtures"])
    assert corpus.get_golden("example.route.second") is not None
    assert corpus.get_golden("missing.route") is None


def test_legacy_singular_golden_manifest_remains_compatible(tmp_path):
    source = ROOT / "benchmarks"
    shutil.copytree(source, tmp_path, dirs_exist_ok=True)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    singular = manifest.pop("golden_fixtures")[0]
    manifest["golden_fixture"] = singular
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    corpus = BenchmarkCorpus.load(tmp_path)
    assert len(corpus.goldens) == 1
    assert corpus.golden is corpus.get_golden(corpus.golden["route_id"])


def test_duplicate_golden_route_identity_is_rejected(tmp_path):
    source = ROOT / "benchmarks"
    shutil.copytree(source, tmp_path, dirs_exist_ok=True)
    duplicate_path = tmp_path / "cross_layer" / "duplicate-golden.json"
    duplicate_path.write_text(
        (tmp_path / "cross_layer" / "jingwei-golden.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["golden_fixtures"].append("cross_layer/duplicate-golden.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="route IDs must be present and unique"):
        BenchmarkCorpus.load(tmp_path)


def test_fixture_files_contain_no_secret_shaped_values_or_sensitive_users():
    corpus = BenchmarkCorpus.load()
    serialized = "\n".join(
        path.read_text(encoding="utf-8") for path in corpus.root.rglob("*.json")
    ).lower()
    assert "authorization: bearer" not in serialized
    assert "amap_api_key=" not in serialized
    assert "openai_api_key=" not in serialized
    assert "password" not in serialized
    assert "email" not in serialized


def test_evaluation_framework_has_no_jingwei_or_changzhi_business_conditions():
    framework = ROOT / "app" / "evaluation"
    text = "\n".join(path.read_text(encoding="utf-8") for path in framework.glob("*.py"))
    for business_value in (
        "jingwei", "fajiushan", "changzhi.route", "changzhi.anchor", "shanxi.changzhi"
    ):
        assert business_value not in text.lower()


def test_secret_audit_rejects_leaking_fixture(tmp_path):
    source = ROOT / "benchmarks"
    for path in source.rglob("*.json"):
        target = tmp_path / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    suite_path = tmp_path / "planning" / "cases.json"
    data = json.loads(suite_path.read_text(encoding="utf-8"))
    data["metadata"] = {"api_key": "SHOULD_NOT_BE_COMMITTED"}
    suite_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="secret leakage"):
        BenchmarkCorpus.load(tmp_path)
