---
document_id: DOC-DEMO-DICOM-001
title: DICOM 비식별화 시스템 점검 예제
document_type: GUIDE
version: 1.0
approval_status: APPROVED
effective_date: 2026-09-01
allowed_roles: [REVIEWER, RADIOLOGIST, QA_RA, ADMIN]
institution_id: DEMO
---
# 연구용 DEMO 문서

원본 DICOM과 픽셀은 지식 검색 저장소에 넣지 않는다. 직접식별 태그를 제거하고 UID는 익명 해시로 취급한다.

## 점검

합성 데이터로 태그 제거, 금지 필드, 로그 마스킹과 내보내기 항목을 시험한다.
