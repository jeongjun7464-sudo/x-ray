import ssl
from io import BytesIO
import httpx
import pydicom
from app.integrations.schemas import AdapterConfig
from app.integrations.orthanc import OrthancAdapter
from app.integrations.dicomweb import DicomWebAdapter
from app.integrations.deidentification import deidentify
from app.integrations.retry import retry_delay
from app.services.synthetic_dicom import generate_synthetic_dicom

def config(**kwargs):
    return AdapterConfig(base_url="https://synthetic.example", enabled=True, **kwargs)

def test_not_configured_never_calls_transport():
    def fail(request): raise AssertionError("unexpected network")
    assert OrthancAdapter(transport=httpx.MockTransport(fail)).health_check().status == "NOT_CONFIGURED"

def test_qido_malformed_elements_fail_closed():
    for element in (None, [], "invalid", {"Value": "invalid"}):
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[{"0020000D": element}]))
        result = DicomWebAdapter(config(), transport=transport).qido_search({})
        assert result.code == "DICOMWEB_INVALID_RESPONSE"
        assert result.data is None

def test_fhir_references_privacy_and_unverified_transmission():
    from app.integrations.fhir import create_bundle, validate_resource, FhirAdapter
    bundle = create_bundle("synthetic-analysis", "CHEST", "dummy-v1", "synthetic-v1")
    assert validate_resource(bundle)["status"] == "LOCAL_CHECKS_PASSED"
    assert FhirAdapter().send_bundle(bundle, "key", True).status == "MANUAL_REVIEW_REQUIRED"
    bundle["entry"][2]["resource"]["subject"]["reference"] = "Patient/foreign"
    assert "FHIR_BROKEN_REFERENCE" in validate_resource(bundle)["errors"]
    bundle["entry"][0]["resource"]["name"] = [{"text": "SYNTHETIC"}]
    assert "FHIR_PHI_FIELD" in validate_resource(bundle)["errors"]

def test_recovery_bounds_and_uncertain_delivery():
    from types import SimpleNamespace
    from app.integrations.recovery import record_failure
    from app.integrations.schemas import IntegrationResult
    class Sink:
        def add(self, value): pass
    def job(): return SimpleNamespace(id="test", status="SENDING", attempt_count=1, max_attempts=3)
    timeout = IntegrationResult("DEGRADED", "DICOMWEB_TIMEOUT", retryable=True)
    row = job()
    assert record_failure(Sink(), row, timeout, "request") == "MANUAL_REVIEW_REQUIRED"
    row = job()
    assert record_failure(Sink(), row, timeout, "request", upstream_idempotency_verified=True) == "RETRY_PENDING"
    assert row.next_attempt_at is not None
    row = job(); row.attempt_count = 3
    assert record_failure(Sink(), row, timeout, "request", upstream_idempotency_verified=True) == "QUARANTINED"
    assert record_failure(Sink(), job(), IntegrationResult("AUTHENTICATION_REQUIRED", "FHIR_AUTH_FAILED", http_status=401), "request", upstream_idempotency_verified=True) == "QUARANTINED"

def test_integration_rules_block_missing_and_critical_evidence():
    from app.services.consistency.engine import ConsistencyEngine
    result = ConsistencyEngine().validate({"integration": {"phi_free": False, "confirmed": False}}, ["MEDICAL_INTEGRATION"])
    assert len(result["findings"]) == 18 and result["high_risk_block"]
    assert "BLOCK_EXTERNAL_TRANSFER" in result["automatic_actions"]
    assert any(row["status"] == "NOT_VERIFIABLE" for row in result["findings"])

def test_health_check_redacts_upstream_fields():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"Version": "test", "PatientName": "SYNTHETIC", "Password": "never-return"}))
    result = OrthancAdapter(config(), transport=transport).health_check()
    assert result.status == "CONNECTED" and result.data == {"version": "test"}

def test_auth_timeout_tls_and_retry_classification():
    for code in (401, 403, 400, 503):
        adapter = OrthancAdapter(config(), transport=httpx.MockTransport(lambda r: httpx.Response(code)))
        result = adapter.health_check()
        assert result.retryable == (code == 503)
    def timeout(request): raise httpx.ReadTimeout("secret must not escape")
    result = OrthancAdapter(config(), transport=httpx.MockTransport(timeout)).health_check()
    assert result.code == "ORTHANC_TIMEOUT" and "secret" not in repr(result)
    def tls(request): raise httpx.ConnectError("private endpoint") from ssl.SSLError("bad certificate")
    result = OrthancAdapter(config(), transport=httpx.MockTransport(tls)).health_check()
    assert result.status == "CERTIFICATE_ERROR" and not result.retryable
    assert retry_delay(1) == 2 and retry_delay(2) == 4 and retry_delay(3) is None

def test_tls_and_confirmation_block_before_network():
    def fail(request): raise AssertionError("unexpected network")
    adapter = OrthancAdapter(config(production=True, verify_tls=False), transport=httpx.MockTransport(fail))
    assert adapter.health_check().status == "CERTIFICATE_ERROR"
    adapter = OrthancAdapter(config(), transport=httpx.MockTransport(fail))
    assert adapter.store_instance(generate_synthetic_dicom(), "key", True).code == "ORTHANC_TRANSMISSION_DISABLED"

def test_gateway_removes_phi_private_and_remaps_uids():
    raw = generate_synthetic_dicom()
    source = pydicom.dcmread(BytesIO(raw))
    source.add_new((0x0011, 0x1010), "LO", "SYNTHETIC-PRIVATE")
    out = BytesIO(); source.save_as(out, enforce_file_format=True)
    result = deidentify(out.getvalue())
    assert result.status == "MANUAL_REVIEW_REQUIRED"
    clean = pydicom.dcmread(BytesIO(result.data["dicom_bytes"]))
    assert "PatientName" not in clean and "PatientID" not in clean
    assert not any(e.tag.is_private for e in clean.iterall())
    assert clean.StudyInstanceUID != source.StudyInstanceUID
    assert result.data["burned_in_annotation_status"] == "NOT_VERIFIED"
    assert deidentify(b"bad").code == "INVALID_DICOM"

def test_qido_allowlist_wado_size_and_stow_partial_contract():
    def search(request):
        assert "PatientName" not in str(request.url)
        return httpx.Response(200, json=[{"0020000D": {"vr": "UI", "Value": ["1.2.3"]}, "00100010": {"Value": ["SYNTHETIC-NAME"]}}], headers={"Content-Type": "application/dicom+json"})
    result = DicomWebAdapter(config(), transport=httpx.MockTransport(search)).qido_search({"PatientName": "excluded"})
    assert len(result.data[0]["study_hash"]) == 64 and "SYNTHETIC-NAME" not in repr(result)
    raw = generate_synthetic_dicom()
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=raw, headers={"Content-Type": "application/dicom"}))
    assert DicomWebAdapter(config(), transport=transport).wado_retrieve("1.2", "1.3", "1.4").status == "MANUAL_REVIEW_REQUIRED"
    assert DicomWebAdapter(config(max_response_bytes=100), transport=transport).wado_retrieve("1.2", "1.3", "1.4").code == "DICOMWEB_RESPONSE_TOO_LARGE"
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"00081198": {"Value": [{}]}, "00081199": {"Value": [{}]}}))
    result = DicomWebAdapter(config(transmission_enabled=True), transport=transport).stow_store(raw, "test-key", True)
    assert result.code == "DICOMWEB_PARTIAL_FAILURE"
