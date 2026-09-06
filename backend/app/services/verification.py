import base64,hashlib,io,json,zipfile
from datetime import datetime,timezone
from app.services.synthetic_dicom import generate_synthetic_dicom

SAFETY_CASES={
"BLUR":("WARNING",True,None),"UNDER_EXPOSURE":("REJECT",True,None),"OVER_EXPOSURE":("REJECT",True,None),"ROTATION":("WARNING",True,None),"HORIZONTAL_FLIP":("WARNING",True,None),"CROPPED_ANATOMY":("WARNING",True,None),"METAL_ARTIFACT":("WARNING",True,None),"EMPTY_PIXEL_DATA":("REJECT",True,"MISSING_PIXEL_DATA"),"CORRUPTED_DICOM":("REJECT",True,"INVALID_FILE"),"PHI_INCLUDED":("WARNING",True,"PHI_DETECTED"),"WRONG_MODALITY":("REJECT",True,"UNSUPPORTED_MODALITY"),"UNSUPPORTED_REGION":("WARNING",True,"OUT_OF_DISTRIBUTION"),"DUPLICATE_SOP":("WARNING",True,"DUPLICATE_SOP"),"MODEL_TIMEOUT":("WARNING",True,"MODEL_TIMEOUT"),"DATABASE_FAILURE":("WARNING",True,"DATABASE_FAILURE")}

def safety_case(name:str)->dict:
    name=name.upper()
    if name not in SAFETY_CASES:raise ValueError("지원하지 않는 합성 안전 사례입니다.")
    quality,review,error=SAFETY_CASES[name];variant={"EMPTY_PIXEL_DATA":"no_pixel","CORRUPTED_DICOM":"corrupt","WRONG_MODALITY":"wrong_modality","PHI_INCLUDED":"normal"}.get(name,"normal")
    return {"case":name,"dicom":generate_synthetic_dicom(variant),"expected_quality_status":quality,"expected_review_required":review,"expected_error_code":error,"synthetic":True,"clinical_use":False}

def fairness(cases:list[dict],group_by:str,min_samples:int=20)->dict:
    allowed={"age_group","sex","equipment","institution","view_position","quality_grade"}
    if group_by not in allowed:raise ValueError("지원하지 않는 공정성 그룹입니다.")
    groups={}
    for row in cases:groups.setdefault(str(row.get(group_by,"UNKNOWN")),[]).append(row)
    output=[]
    for name,rows in sorted(groups.items()):
        n=len(rows)
        if n<min_samples:output.append({"group":name,"sample_size":n,"status":"INSUFFICIENT_DATA","metrics":None});continue
        tp=sum(bool(x.get("truth")) and bool(x.get("prediction")) for x in rows);tn=sum(not x.get("truth") and not x.get("prediction") for x in rows);fp=sum(not x.get("truth") and bool(x.get("prediction")) for x in rows);fn=sum(bool(x.get("truth")) and not x.get("prediction") for x in rows)
        div=lambda a,b:a/b if b else None;precision=div(tp,tp+fp);recall=div(tp,tp+fn)
        positives=[x for x in rows if bool(x.get("truth"))];negatives=[x for x in rows if not bool(x.get("truth"))]
        auroc=None
        if positives and negatives and all("score" in x for x in rows):
            wins=sum((p["score"]>q["score"])+.5*(p["score"]==q["score"]) for p in positives for q in negatives)
            auroc=wins/(len(positives)*len(negatives))
        output.append({"group":name,"sample_size":n,"status":"MEASURED","metrics":{"sensitivity":recall,"specificity":div(tn,tn+fp),"precision":precision,"recall":recall,"f1":(2*precision*recall/(precision+recall) if precision is not None and recall is not None and precision+recall else None),"auroc":auroc,"false_positive_rate":div(fp,fp+tn),"false_negative_rate":div(fn,fn+tp)}})
    return {"group_by":group_by,"groups":output,"warning":"그룹 간 차이는 검토 경고이며 개인의 민감 특성을 예측하지 않습니다."}

def _xlsx(title:str,headers:list[str])->bytes:
    """Create a small standards-compliant XLSX without an optional spreadsheet dependency."""
    esc=lambda value:str(value).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    rows=[headers,[title]+["" for _ in headers[1:]]]
    sheet="".join("<row r='%d'>%s</row>"%(i+1,"".join("<c r='%s%d' t='inlineStr'><is><t>%s</t></is></c>"%(chr(65+j),i+1,esc(v)) for j,v in enumerate(row))) for i,row in enumerate(rows))
    parts={"[Content_Types].xml":b'''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>''',"_rels/.rels":b'''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',"xl/workbook.xml":b'''<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Records" sheetId="1" r:id="rId1"/></sheets></workbook>''',"xl/_rels/workbook.xml.rels":b'''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>''',"xl/worksheets/sheet1.xml":("<?xml version='1.0' encoding='UTF-8'?><worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData>"+sheet+"</sheetData></worksheet>").encode()}
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)
    return out.getvalue()

def build_audit_package(role:str,versions:dict)->tuple[bytes,dict]:
    created=datetime.now(timezone.utc).isoformat();files={"requirements.pdf":b"%PDF-1.4\n% Research validation requirements\n%%EOF","risk-management.xlsx":_xlsx("Risk register export",["risk_id","control","verification_test","residual_risk"]),"dataset-specification.pdf":b"%PDF-1.4\n% Dataset specification\n%%EOF","model-card.pdf":b"%PDF-1.4\n% Model card\n%%EOF","validation-report.pdf":b"%PDF-1.4\n% Validation report: no clinical metrics\n%%EOF","approval-history.csv":b"id,status,approver\n","change-history.csv":b"id,action,request_id\n","capa-records.csv":b"id,status,error_type\n","traceability-matrix.xlsx":_xlsx("Traceability export",["requirement_id","risk_id","implementation","api","test_id","result"])}
    manifest={"files":[{"filename":name,"sha256":hashlib.sha256(data).hexdigest(),"created_at":created,"related_versions":versions,"creator_role":role} for name,data in files.items()]}
    files["manifest.json"]=json.dumps(manifest,ensure_ascii=False,sort_keys=True).encode();out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    return out.getvalue(),manifest

def encode(data:bytes)->str:return base64.b64encode(data).decode()
def decode(data:str)->bytes:return base64.b64decode(data)
