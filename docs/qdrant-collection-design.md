# Qdrant Collection 설계

Collection은 `xray_knowledge`, cosine dense vector 기본 크기는 384다. payload는 문서/청크 ID, 제목, 유형, 버전, 섹션, 내용, 경로, 승인·유효기간·허용 역할·기관·언어, content hash와 embedding 모델만 포함한다. 승인·역할·기관·만료·비활성 필터를 적용한다. 환자 식별정보, 원본 DICOM, X-ray 픽셀, 비밀키와 토큰은 저장하지 않는다. URL과 키는 환경변수이며 상태 API에도 노출하지 않는다.
