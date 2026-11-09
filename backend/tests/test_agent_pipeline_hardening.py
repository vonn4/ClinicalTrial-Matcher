"""End-to-end five-agent reliability checks with no network or real credentials.

Real-format public trial records are mocked; only the user's own computer can
verify actual ClinicalTrials.gov/Gemini connectivity and full browser behavior.
"""
from __future__ import annotations
import asyncio
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.agents import discovery_agent
from app.agents.budget import AgentBudget
from app.llm import ModelUnavailable
from app.schemas import TrialRecord

client = TestClient(app)
TOKEN = "test-team-token-strong-and-private"


def setup_model(monkeypatch):
    monkeypatch.setenv("ENABLE_LIVE_AI", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-no-real-provider-key")
    monkeypatch.setenv("LIVE_AI_ACCESS_TOKEN", TOKEN)
    monkeypatch.setenv("MAX_AGENT_MODEL_CALLS_PER_HOUR", "24")


def person(age="42", condition="multiple sclerosis"):
    answers = {
        "condition": {"state": "answered", "value": condition},
        "age": {"state": "answered", "value": age},
    }
    profile = client.post("/api/v1/intake/profile", json={
        "answers": answers, "synthetic": True
    })
    assert profile.status_code == 200, profile.text
    return profile.json()


def trial(nct="NCT12345678"):
    return TrialRecord(
        nct_id=nct, title="Public-record-shaped test fixture", source="clinicaltrials.gov",
        status="RECRUITING", conditions=["Multiple Sclerosis"], phase=["PHASE2"],
        minimum_age="18 Years", eligibility_text=(
            "Inclusion Criteria:\n- Participants aged 18 years or older\n"
            "Exclusion Criteria:\n- A history of severe active infection"
        ), brief_summary="Synthetic study fixture used only inside automated tests."
    )


def test_live_pipeline_falls_back_when_gemini_discovery_fails(monkeypatch):
    setup_model(monkeypatch)
    async def search(query, limit=80):
        return [trial()]
    async def fail_choice(self, *, model, system, payload):
        if "allowed_terms" in payload:
            raise ModelUnavailable("test-only optional selection failed")
        if "criteria" in payload:
            return {"assessments": [
                {"criterion_id": c["id"], "status": "unknown", "patient_evidence": [],
                 "explanation": "No explicit source evidence supplied."}
                for c in payload["criteria"]
            ]}
        return {"ordered_fact_keys": [q["fact_key"] for q in payload.get("questions", [])]}
    monkeypatch.setattr(discovery_agent, "search_trials", search)
    monkeypatch.setattr(AgentBudget, "generate", fail_choice)
    response = client.post("/api/v1/matching/analyze",
        headers={"X-Live-Access-Token": TOKEN},
        json={"mode":"live","depth":"model","profile":person(condition="sickle cell disease"),"max_studies":1})
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["trials"]) == 1
    assert result["trials"][0]["source"] == "clinicaltrials.gov"
    assert result["trials"][0]["nct_id"] == "NCT12345678"
    assert result["trace"][1]["details"]["model_fallback"] is True
    assert result["trace"][1]["execution"] == "tools"
    assert result["trace"][2]["execution"] == "model"
    assert result["trace"][3]["execution"] == "model"


def test_partial_primary_model_failure_preserves_other_agent_work(monkeypatch):
    setup_model(monkeypatch)
    records = [trial("NCT12345678"), trial("NCT23456789"), trial("NCT34567890")]
    async def search(query, limit=80):
        return records
    calls = {"primary": 0}
    async def intermittent_model(self, *, model, system, payload):
        if "criteria" in payload:
            if payload.get("role") == "primary_analyst":
                calls["primary"] += 1
                if calls["primary"] == 2:
                    raise ModelUnavailable("synthetic quota test")
            return {"assessments": [
                {"criterion_id": c["id"], "status": "unknown", "patient_evidence": [],
                 "explanation": "Unable to establish a complete criterion match."}
                for c in payload["criteria"]
            ]}
        return {"ordered_fact_keys": [q["fact_key"] for q in payload.get("questions", [])]}
    monkeypatch.setattr(discovery_agent, "search_trials", search)
    monkeypatch.setattr(AgentBudget, "generate", intermittent_model)
    response = client.post("/api/v1/matching/analyze",
        headers={"X-Live-Access-Token": TOKEN},
        json={"mode":"live","depth":"model","profile":person(),"max_studies":3})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["assessments"]) == 3
    assert [a["provenance"] for a in data["assessments"]].count("live_llm") == 2
    assert [a["provenance"] for a in data["assessments"]].count("deterministic_followup") == 1
    assert data["trace"][2]["details"]["model_failures"] == 1
    assert data["trace"][3]["details"]["independent_trials"] == 2


def test_failed_independent_skeptic_cannot_silently_clear_trial(monkeypatch):
    setup_model(monkeypatch)
    async def search(query, limit=80):
        return [trial()]
    async def model_failure(self, *, model, system, payload):
        if payload.get("role") == "independent_skeptic":
            raise ModelUnavailable("test-only skeptic unavailable")
        if "criteria" in payload:
            return {"assessments": [
                {"criterion_id": c["id"], "status": "unknown",
                 "explanation": "Unresolved", "patient_evidence": []}
                for c in payload["criteria"]
            ]}
        return {"ordered_fact_keys": [q["fact_key"] for q in payload.get("questions", [])]}
    monkeypatch.setattr(discovery_agent, "search_trials", search)
    monkeypatch.setattr(AgentBudget, "generate", model_failure)
    response = client.post("/api/v1/matching/analyze",
        headers={"X-Live-Access-Token": TOKEN},
        json={"mode":"live","depth":"model","profile":person(),"max_studies":1})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["trace"][3]["details"]["model_failures"] == 1
    assessment = data["assessments"][0]
    assert assessment["provenance"] == "live_llm"
    assert assessment["summary"] == "clinical_review"
    assert assessment["skeptic"] == []
    assert any("Independent AI skeptic review not completed" in x for x in assessment["unresolved"])


def test_live_search_failure_never_substitutes_test_fixtures(monkeypatch):
    async def search(query, limit=80):
        raise RuntimeError("Official registry offline in test fixture")
    monkeypatch.setattr(discovery_agent, "search_trials", search)
    with pytest.raises(RuntimeError, match="Official registry offline"):
        asyncio.run(discovery_agent.execute(
            profile=__import__("app.schemas",fromlist=["PatientProfile"]).PatientProfile.model_validate(person()),
            mode=__import__("app.schemas",fromlist=["Mode"]).Mode.live,
            count=3, selected_ids=[], model=False, budget=AgentBudget()))


def test_model_probe_requires_explicit_free_tier_confirmation(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    script = Path(__file__).resolve().parents[2] / "run_local.py"
    cp = subprocess.run([sys.executable, str(script), "--probe-ai"],
                        capture_output=True, text=True, timeout=10)
    assert cp.returncode != 0
    assert "--confirm-free-tier" in cp.stderr
