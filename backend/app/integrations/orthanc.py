import re
from .base import HttpAdapter
from .schemas import IntegrationResult
from .security import anonymous_uid

class OrthancAdapter(HttpAdapter):
    provider = "ORTHANC"
    def health_check(self):
        result = self.json_result(self.request("GET", "/system"), dict)
        if result.status != "CONNECTED":
            return result
        if not isinstance(result.data.get("Version"), str):
            return IntegrationResult("DEGRADED", "ORTHANC_INVALID_RESPONSE", mode=result.mode)
        return IntegrationResult("CONNECTED", data={"version": result.data["Version"]}, mode=result.mode)

    def _search(self, level, query):
        allowed = {"StudyDate", "Modality", "BodyPartExamined"}
        clean = {key: str(value) for key, value in query.items() if key in allowed}
        result = self.json_result(self.request("POST", "/tools/find", read_only=True, json={"Level": level, "Query": clean, "Expand": True, "Limit": 100}), list)
        if result.status != "CONNECTED":
            return result
        items = []
        for entry in result.data:
            if not isinstance(entry, dict):
                return IntegrationResult("DEGRADED", "ORTHANC_INVALID_RESPONSE", mode=result.mode)
            tags = entry.get("MainDicomTags", {})
            uid = tags.get("StudyInstanceUID" if level == "Study" else "SeriesInstanceUID")
            if uid:
                items.append({"uid_hash": anonymous_uid(str(uid))})
        return IntegrationResult("CONNECTED", data=items, mode=result.mode)

    def search_studies(self, query): return self._search("Study", query)
    def search_series(self, query): return self._search("Series", query)
    def retrieve_instance(self, instance_id):
        if not re.fullmatch(r"[a-f0-9-]{36,64}", instance_id):
            return IntegrationResult("DISCONNECTED", "ORTHANC_INVALID_INSTANCE_ID")
        from .deidentification import deidentify
        result = self.request("GET", f"/instances/{instance_id}/file")
        if result.status != "CONNECTED": return result
        if result.data["content_type"].split(";")[0] != "application/dicom":
            return IntegrationResult("DEGRADED", "ORTHANC_INVALID_RESPONSE")
        return deidentify(result.data["bytes"])

    def store_instance(self, data, idempotency_key, confirmed=False):
        # Transport contract only; the service must authorize and deidentify first.
        if len(data) < 132 or data[128:132] != b"DICM":
            return IntegrationResult("DEGRADED", "ORTHANC_INVALID_DICOM")
        result = self.json_result(self.request("POST", "/instances", content=data, confirmed=confirmed, idempotency_key=idempotency_key, headers={"Content-Type": "application/dicom"}), dict)
        if result.status != "CONNECTED": return result
        status = result.data.get("Status")
        if status not in {"Success", "AlreadyStored"}:
            return IntegrationResult("DEGRADED", "ORTHANC_INVALID_RESPONSE")
        return IntegrationResult("CONNECTED" if status == "Success" else "DEGRADED", "ORTHANC_DUPLICATE_INSTANCE" if status == "AlreadyStored" else None, data={"stored": status == "Success"})
    def store_report(self, data, idempotency_key, confirmed=False):
        return self.store_instance(data, idempotency_key, confirmed)
    def get_capabilities(self):
        return {"provider": self.provider, "operations": ["search_studies", "search_series", "retrieve_instance", "store_instance"], "network_verified": False}
