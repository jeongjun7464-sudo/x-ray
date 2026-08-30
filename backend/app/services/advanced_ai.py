import hashlib
import platform
import time
from io import BytesIO

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from app.core.config import settings
from app.services.differentiators import assess_extended
from app.services.policy import review_decision
from app.services.quality import assess_image_quality

def _stage(name: str, version: str, started: float, output: dict, confidence: float | None=None, status="COMPLETED") -> dict:
    return {"stage":name,"model_version":version,"status":status,"output":output,"confidence":confidence,"processing_time_ms":max(0,round((time.perf_counter()-started)*1000,3))}

def run_multistage(validation, top: list[dict], digest: str, laterality: str, view: str, body: str | None) -> dict:
    stages=[]; start=time.perf_counter()
    modality=str(getattr(validation.dicom,"Modality","")).upper() if validation.dicom is not None else None
    distribution="IN_DISTRIBUTION" if modality in {"DX","CR","RG"} else "UNKNOWN" if validation.dicom is None else "OUT_OF_DISTRIBUTION"
    stages.append(_stage("XRAY_GATE","dicom-modality-gate-v1",start,{"distribution":distribution,"modality":modality or "UNAVAILABLE"},1.0 if distribution=="IN_DISTRIBUTION" else 0.0))
    if distribution!="IN_DISTRIBUTION":
        stages.append(_stage("PIPELINE_STOP","safety-policy-v1",time.perf_counter(),{"reason":"XRAY_NOT_CONFIRMED","route":"MANUAL_REVIEW"},status="STOPPED"))
        return {"status":"STOPPED","final_route":"MANUAL_REVIEW","stages":stages}
    broad={"CHEST":"TORSO","ABDOMEN":"TORSO","SPINE":"TORSO","PELVIS":"TORSO","HAND_WRIST":"UPPER_EXTREMITY","SHOULDER_ARM":"UPPER_EXTREMITY","KNEE":"LOWER_EXTREMITY","FOOT_ANKLE":"LOWER_EXTREMITY"}.get(top[0]["class"],"UNKNOWN")
    stages.append(_stage("BODY_GROUP","dummy-body-group-v1",time.perf_counter(),{"class":broad},top[0]["confidence"]))
    stages.append(_stage("ANATOMICAL_REGION",settings.model_version,time.perf_counter(),{"class":top[0]["class"],"top3":top},top[0]["confidence"]))
    stages.append(_stage("LATERALITY","dicom-metadata-v1",time.perf_counter(),{"laterality":laterality},1.0 if laterality!="UNKNOWN" else 0.0))
    stages.append(_stage("VIEW_POSITION","dicom-metadata-v1",time.perf_counter(),{"view_position":view},1.0 if view!="UNKNOWN" else 0.0))
    quality=assess_image_quality(validation.pixels); quality_status="REJECT" if quality.score<.2 else "WARNING" if quality.reasons else "PASS"; stages.append(_stage("IMAGE_QUALITY","heuristic-quality-v2",time.perf_counter(),{"status":quality_status,"reasons":list(quality.reasons)},quality.score))
    extended=assess_extended(validation.pixels,top,validation.dicom,quality); stages.append(_stage("UNCERTAINTY_OOD","entropy-policy-v1",time.perf_counter(),{"distribution":extended.distribution_status,"entropy":extended.entropy},top[0]["confidence"]))
    required,reasons=review_decision(top,laterality,view,body,tuple(set(quality.reasons)|set(extended.metadata_warnings))); route="MANUAL_REVIEW" if required else extended.routing_target
    stages.append(_stage("ROUTING","review-routing-policy-v2",time.perf_counter(),{"route":route,"review_required":required,"reasons":reasons},1.0))
    return {"status":"COMPLETED","final_route":route,"stages":stages}

def detection_interface(width: int, height: int, enabled: bool) -> dict:
    if not enabled: return {"status":"NOT_AVAILABLE","model":"NONE","detections":[],"reason":"위치 라벨과 검증된 탐지 모델이 없어 기능 플래그가 비활성화되었습니다."}
    return {"status":"INTERFACE_READY_NO_MODEL","model":"NONE","detections":[],"annotation_format":"COCO_XYWH","image_size":[width,height]}

def landmark_interface(region: str) -> dict:
    expected={"KNEE":["KNEE_JOINT_CENTER"],"HAND_WRIST":["WRIST_JOINT"],"SHOULDER":["SHOULDER_JOINT"],"PELVIS_HIP":["PELVIS_CENTER"],"SPINE":["SPINE_CENTERLINE"]}.get(region,[])
    return {"status":"LABELING_REQUIRED","region":region,"expected_landmarks":expected,"predictions":[],"reason":"검증된 랜드마크 학습 데이터가 없습니다."}

def preprocessing_comparison(pixels) -> list[dict]:
    image=pixels if isinstance(pixels,Image.Image) else Image.fromarray(pixels); gray=image.convert("L"); arr=np.asarray(gray,dtype=np.float32)
    variants={"original":arr,"min_max":(arr-arr.min())/(max(1,float(arr.max()-arr.min())))*255,"z_score":np.clip((arr-arr.mean())/(arr.std()+1e-6)*32+128,0,255),"center_crop":np.asarray(gray.crop((gray.width//10,gray.height//10,gray.width-gray.width//10,gray.height-gray.height//10)).resize(gray.size))}
    return [{"method":k,"shape":list(v.shape),"mean":float(v.mean()),"std":float(v.std()),"output_hash":hashlib.sha256(v.astype(np.uint8).tobytes()).hexdigest()} for k,v in variants.items()]

def stress_test(pixels) -> dict:
    image=(pixels if isinstance(pixels,Image.Image) else Image.fromarray(pixels)).convert("L"); base=assess_image_quality(image).score
    variants={"brightness":ImageEnhance.Brightness(image).enhance(1.5),"contrast":ImageEnhance.Contrast(image).enhance(.5),"blur":image.filter(ImageFilter.GaussianBlur(2)),"rotate":image.rotate(7),"horizontal_flip":image.transpose(Image.Transpose.FLIP_LEFT_RIGHT),"resolution_down":image.resize((max(16,image.width//4),max(16,image.height//4))).resize(image.size),"compression":_jpeg(image)}
    rows=[]
    for name,value in variants.items():
        score=assess_image_quality(value).score; rows.append({"transformation":name,"quality_score":score,"score_change":score-base,"medical_use_warning":"견고성 시험 전용; 자동 학습 증강으로 사용하지 않음"})
    return {"baseline_quality_score":base,"variants":rows,"model_performance_evaluated":False,"reason":"정답 라벨과 승인 모델이 없어 품질 점수 변화만 측정했습니다."}

def _jpeg(image):
    out=BytesIO();image.save(out,"JPEG",quality=35);return Image.open(BytesIO(out.getvalue())).copy()

def reproducibility_manifest(dataset_version="UNSPECIFIED", seed=42) -> dict:
    return {"python_version":platform.python_version(),"platform":platform.platform(),"random_seed":seed,"dataset_version":dataset_version,"label_mapping_version":"1.0","preprocessing_config":"default-v1","model_structure":"DenseNet121 interface","model_version":settings.model_version,"cuda_version":"NOT_QUERIED","gpu":"NOT_REQUIRED_DUMMY_MODE","rerun_command":f"PYTHONPATH=ml python ml/train.py --seed {seed} --dataset-version {dataset_version}","checkpoint_hash":None,"metrics":None}
