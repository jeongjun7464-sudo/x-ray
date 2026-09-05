# Phase 23 — AI 리터러시 및 책임 있는 AI 구현 상태

## 구현 완료

- 결과 설명, 단계별 latency, 역할별 교육, 퀴즈, 모델·데이터셋 카드와 한국어 용어사전을 제공한다.
- 동의 버전·확인 시각을 저장하고 오분류 신고를 검토 작업 및 CAPA 후보에 연결한다.
- 책임 있는 AI 지표와 12개 위험 등록부를 API 및 자동 테스트에 연결한다.
- 키보드 탐색, label, 텍스트+아이콘 상태, 그래프 대체 표와 해결 방법이 포함된 오류 메시지를 제공한다.

## 정직한 제한사항

- 기본 모델은 학습되지 않은 `DEMO / DUMMY` 모델이다.
- 임상 정확도, AUROC, 하위그룹 성능과 GPU 속도는 측정하지 않았으며 화면에 수치를 만들지 않는다.
- 처리량은 저장된 기록의 집계 수이며 실제 부하시험 TPS가 아니다.
- 접근성 자동화는 기본 DOM/label 검증이며 WCAG 전문 감사를 대체하지 않는다.

## 검증

- 백엔드: `backend/tests/test_responsible_ai.py`
- 프론트엔드: `frontend/src/App.test.tsx`
- 마이그레이션: `backend/alembic/versions/0006_responsible_ai.py`
