"""Research-only FHIR R4 collection. Local checks are not full conformance validation."""
import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone
from .base import HttpAdapter
from .schemas import IntegrationResult

def create_bundle(analysis_id: str, region: str, model_version: str, dataset_version: str) -> dict:
    # Hash all externally supplied identifiers; never serialize source descriptions.
    alias = hashlib.sha256(analysis_id.encode()).hexdigest()
    kinds = ("Patient", "Device", "ImagingStudy", "Observation", "DiagnosticReport", "DocumentReference", "Provenance", "AuditEvent")
    urls = {kind: "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "xray-research:" + alias + ":" + kind)) for kind in kinds}
    ref = lambda kind: {"reference": urls[kind]}
    now = datetime.now(timezone.utc).isoformat()
    safe_region = region if region in {"CHEST", "SPINE", "HAND_WRIST", "KNEE", "UNKNOWN", "ANKLE", "PELVIS", "ELBOW", "SHOULDER"} else "UNKNOWN"
    resources = [
        {"resourceType": "Patient", "identifier": [{"system": "urn:xray:anonymous-analysis", "value": alias}]},
        {"resourceType": "Device", "deviceName": [{"name": "Research AI pipeline", "type": "model-name"}],
         "version": [{"value": hashlib.sha256(model_version.encode()).hexdigest()}]},
        {"resourceType": "ImagingStudy", "status": "available", "subject": ref("Patient")},
        {"resourceType": "Observation", "status": "preliminary", "code": {"text": "Research anatomical routing output"},
         "subject": ref("Patient"), "device": ref("Device"), "valueString": safe_region},
        {"resourceType": "DiagnosticReport", "status": "preliminary", "code": {"text": "Research-only routing report"},
         "subject": ref("Patient"), "result": [ref("Observation")], "imagingStudy": [ref("ImagingStudy")]},
        {"resourceType": "DocumentReference", "status": "current", "subject": ref("Patient"),
         "content": [{"attachment": {"contentType": "text/plain", "data": base64.b64encode(b"RESEARCH ONLY. Not a diagnosis. Human review required.").decode()}}]},
        {"resourceType": "Provenance", "target": [ref("DiagnosticReport"), ref("Observation")], "recorded": now,
         "agent": [{"who": ref("Device")}], "entity": [{"role": "source", "what": {"identifier": {"system": "urn:xray:dataset-version-hash", "value": hashlib.sha256(dataset_version.encode()).hexdigest()}}}]},
        {"resourceType": "AuditEvent", "type": {"system": "http://terminology.hl7.org/CodeSystem/audit-event-type", "code": "rest"},
         "action": "E", "recorded": now, "outcome": "0", "agent": [{"who": ref("Device"), "requestor": False}],
         "source": {"observer": ref("Device")}, "entity": [{"what": ref("DiagnosticReport")}]}]
    for resource in resources:
        resource["id"] = urls[resource["resourceType"]].split(":")[-1]
        resource["meta"] = {"tag": [{"system": "urn:xray:use", "code": "RESEARCH_ONLY"}]}
    return {"resourceType": "Bundle", "type": "collection", "entry": [{"fullUrl": urls[r["resourceType"]], "resource": r} for r in resources]}

def validate_resource(bundle: dict) -> dict:
    errors = []
    if bundle.get("resourceType") != "Bundle" or bundle.get("type") != "collection":
        errors.append("FHIR_INVALID_BUNDLE")
    entries = bundle.get("entry", [])
    if not isinstance(entries, list) or not entries:
        return {"status": "FAILED", "errors": ["FHIR_EMPTY_BUNDLE"], "full_schema_status": "NOT_VERIFIED"}
    urls = [e.get("fullUrl") for e in entries if isinstance(e, dict)]
    if len(urls) != len(entries) or None in urls or len(set(urls)) != len(urls):
        errors.append("FHIR_DUPLICATE_OR_MISSING_FULLURL")
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"name", "telecom", "address", "birthDate", "PatientName", "PatientID"}:
                    errors.append("FHIR_PHI_FIELD")
                if key == "reference" and item not in urls:
                    errors.append("FHIR_BROKEN_REFERENCE")
                if key == "resourceType" and item not in {"Bundle", "Patient", "Device", "ImagingStudy", "Observation", "DiagnosticReport", "DocumentReference", "Provenance", "AuditEvent"}:
                    errors.append("FHIR_UNSUPPORTED_RESOURCE")
                walk(item)
        elif isinstance(value, list):
            for item in value: walk(item)
    # DeviceName.name is a fixed application label, not a person name.
    safe_copy = json.loads(json.dumps(bundle))
    for entry in safe_copy.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Device":
            resource.pop("deviceName", None)
        if resource.get("resourceType") in {"Observation", "DiagnosticReport"} and resource.get("status") != "preliminary":
            errors.append("FHIR_RESEARCH_STATUS_REQUIRED")
    walk(safe_copy)
    return {"status": "FAILED" if errors else "LOCAL_CHECKS_PASSED", "errors": sorted(set(errors)),
            "full_schema_status": "NOT_VERIFIED", "transmission_allowed": False,
            "bundle_sha256": hashlib.sha256(json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}

class FhirAdapter(HttpAdapter):
    provider = "FHIR"
    create_bundle = staticmethod(create_bundle)
    validate_resource = staticmethod(validate_resource)
    def health_check(self):
        result = self.json_result(self.request("GET", "/metadata", headers={"Accept": "application/fhir+json"}), dict)
        if result.status != "CONNECTED": return result
        if result.data.get("resourceType") != "CapabilityStatement" or not str(result.data.get("fhirVersion", "")).startswith("4.0"):
            return IntegrationResult("DEGRADED", "FHIR_INVALID_RESPONSE")
        return IntegrationResult("CONNECTED", data={"fhirVersion": result.data["fhirVersion"]}, mode=result.mode)
    def send_bundle(self, bundle, idempotency_key, confirmed=False):
        validation = validate_resource(bundle)
        if validation["errors"]:
            return IntegrationResult("MANUAL_REVIEW_REQUIRED", "FHIR_VALIDATION_FAILED")
        return IntegrationResult("MANUAL_REVIEW_REQUIRED", "FHIR_FULL_VALIDATOR_NOT_CONFIGURED")
    def read_resource(self, resource_type, resource_id):
        # Retrieval needs institution mapping and resource-specific PHI filtering.
        return IntegrationResult("MANUAL_REVIEW_REQUIRED", "FHIR_READ_GATEWAY_NOT_CONFIGURED")
