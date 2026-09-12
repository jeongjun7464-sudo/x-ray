import re
import uuid
from .base import HttpAdapter
from .schemas import IntegrationResult
from .security import anonymous_uid
from .deidentification import deidentify

def _values(item, tag):
    """Reject malformed DICOM JSON without exposing the upstream payload."""
    element = item.get(tag, {})
    if not isinstance(element, dict):
        raise ValueError("invalid DICOM JSON element")
    values = element.get("Value", [])
    if not isinstance(values, list):
        raise ValueError("invalid DICOM JSON values")
    return values

class DicomWebAdapter(HttpAdapter):
    provider = "DICOMWEB"
    def health_check(self):
        result = self.qido_search({"limit": 1})
        return IntegrationResult(result.status, result.code, http_status=result.http_status, retryable=result.retryable, mode=result.mode)

    def qido_search(self, query, level="studies"):
        if level not in {"studies", "series", "instances"}:
            return IntegrationResult("DISCONNECTED", "DICOMWEB_INVALID_QUERY")
        allowed = {"StudyDate", "Modality", "BodyPartExamined", "limit", "offset"}
        params = {key: str(value) for key, value in query.items() if key in allowed}
        try:
            params["limit"] = str(min(100, max(1, int(params.get("limit", 25)))))
            params["offset"] = str(max(0, int(params.get("offset", 0))))
        except ValueError:
            return IntegrationResult("DISCONNECTED", "DICOMWEB_INVALID_QUERY")
        result = self.json_result(self.request("GET", "/" + level, params=params, headers={"Accept": "application/dicom+json"}), list)
        if result.status != "CONNECTED": return result
        output = []
        for item in result.data:
            if not isinstance(item, dict):
                return IntegrationResult("DEGRADED", "DICOMWEB_INVALID_RESPONSE")
            clean = {}
            for tag, name in (("0020000D", "study_hash"), ("0020000E", "series_hash"), ("00080018", "sop_hash")):
                try:
                    value = _values(item, tag)
                except ValueError:
                    return IntegrationResult("DEGRADED", "DICOMWEB_INVALID_RESPONSE")
                if value and isinstance(value[0], str): clean[name] = anonymous_uid(value[0])
            if not clean:
                return IntegrationResult("DEGRADED", "DICOMWEB_INVALID_RESPONSE")
            output.append(clean)
        return IntegrationResult("CONNECTED", data=output, mode=result.mode)

    def wado_retrieve(self, study_uid, series_uid, sop_uid):
        if not all(re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", uid) and len(uid) <= 64 for uid in (study_uid, series_uid, sop_uid)):
            return IntegrationResult("DISCONNECTED", "DICOMWEB_INVALID_UID")
        result = self.request("GET", f"/studies/{study_uid}/series/{series_uid}/instances/{sop_uid}", headers={"Accept": "application/dicom"})
        if result.status != "CONNECTED": return result
        if result.data["content_type"].split(";")[0].strip() != "application/dicom":
            return IntegrationResult("DEGRADED", "DICOMWEB_INVALID_RESPONSE")
        return deidentify(result.data["bytes"])

    def stow_store(self, data, idempotency_key, confirmed=False):
        if len(data) < 132 or data[128:132] != b"DICM":
            return IntegrationResult("DEGRADED", "DICOMWEB_INVALID_DICOM")
        boundary = "xray-" + uuid.uuid4().hex
        payload = f"--{boundary}\r\nContent-Type: application/dicom\r\n\r\n".encode() + data + f"\r\n--{boundary}--\r\n".encode()
        result = self.json_result(self.request("POST", "/studies", content=payload, confirmed=confirmed, idempotency_key=idempotency_key, headers={"Content-Type": f'multipart/related; type="application/dicom"; boundary={boundary}', "Accept": "application/dicom+json"}), dict)
        if result.status != "CONNECTED": return result
        try:
            failed = _values(result.data, "00081198")
            stored = _values(result.data, "00081199")
        except ValueError:
            return IntegrationResult("DEGRADED", "DICOMWEB_INVALID_RESPONSE")
        if failed:
            return IntegrationResult("DEGRADED", "DICOMWEB_PARTIAL_FAILURE", data={"stored_count": len(stored), "failed_count": len(failed)})
        if not stored:
            return IntegrationResult("DEGRADED", "DICOMWEB_INVALID_RESPONSE")
        return IntegrationResult("CONNECTED", data={"stored_count": len(stored)}, mode=result.mode)
