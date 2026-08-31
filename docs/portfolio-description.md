# AI 기반 X-ray 촬영 부위 자동 분류 및 의료영상 라우팅 시스템

## 한 줄 소개

DICOM X-ray 영상을 비식별화하고 촬영 부위·방향·영상 품질을 자동 분류한 뒤, 신뢰도 기반 검토와 분석 파이프라인 연결을 지원하는 의료영상 AI 웹서비스.

## 프로젝트 확장: LangGraph 기반 의료영상 AI Workflow Agent

X-ray 촬영 부위 분류 결과와 의료영상 시스템 상태를 도구 기반으로 조회하고, RAG 근거를 활용해 검토·장애 분석·검증 문서 생성을 지원하는 Human-in-the-loop AI Agent.

LangGraph 상태 기반 orchestration, 도구 호출, Pydantic structured input, 로컬 하이브리드 RAG, 개인정보 최소화, 역할 기반 접근, 근거 검증, Agent 평가·trace를 FastAPI와 React에 연결했다. 현재 외부 LLM과 벡터 DB는 연결하지 않았으므로 LangChain/LangGraph 외의 미사용 후보 기술을 실제 구현으로 표현하지 않는다.

## 담당 역할과 구현

FastAPI/SQLAlchemy API, pydicom 픽셀 파이프라인, 교체 가능한 추론 인터페이스, 검토 정책, React 대시보드, DenseNet 학습·평가 골격, Docker/CI와 보안 문서를 설계·구현했다. 파일명을 신뢰하지 않는 다중 검증과 PHI 비저장 구조로 업로드 위험을 줄였으며, 모델이 불확실할 때 강제 확정하지 않고 human review로 라우팅했다.

실제 적용 역량은 DICOM 처리, PyTorch 분류 구조, Grad-CAM 모듈, FastAPI API, React 의료영상 UI, 환자 단위 데이터 누수 방지, 사람 검토 기반 능동학습, 요구사항·위험·테스트 추적성이다. MONAI, Orthanc/DICOMweb, MLflow와 DVC는 현재 연결되지 않았으므로 실제 사용 기술로 주장하지 않는다.

## 정량 평가

현재 실제 의료 데이터로 측정한 Accuracy/F1은 없다. 평가 파이프라인은 Accuracy, Macro F1, 클래스별 Precision/Recall/F1, confusion matrix, ECE를 산출하며 데이터 확보 후 결과를 기록한다.

## 직무 연관성

의료영상 전처리, 데이터 누수 방지, calibration과 human-in-the-loop 설계뿐 아니라 API·DB·보안·프론트엔드·배포까지 end-to-end 제품화 역량을 보여준다.

## 예상 질문

- 왜 더미 모드인가? 가중치/민감 데이터 없이 전체 제품 흐름을 재현하기 위해서이며 실제 성능으로 표현하지 않는다.
- 왜 해시만 저장하는가? 중복 추적은 가능하게 하면서 원본과 직접식별정보 보존을 피하기 위해서다.
- 데이터 누수는 어떻게 막나? patient_group_id 기준 분할 검증과 기관 외부 평가를 사용한다.
- 신뢰도는 확률인가? softmax는 보정되지 않을 수 있으므로 ECE를 측정하고 temperature scaling 등 별도 calibration이 필요하다.
- 임상 적용 전 무엇이 필요한가? 다기관/전향 검증, subgroup·실패모드 분석, 보안·개인정보 평가, 사용자 연구, 규제 승인이다.
