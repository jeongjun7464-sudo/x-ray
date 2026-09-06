# 임상 검토 워크플로

Study import 시 AP/PA/LATERAL을 익명 UID 해시로 그룹화하고 중복 SOP와 필수 방향 누락을 검사한다. 영상별 결과와 Study 종합 결과를 분리하며 부위 충돌, OOD, 품질 거부와 높은 소견 점수는 검토 사유로 기록한다.

`HIGH_PRIORITY_REVIEW`는 응급 진단이 아니라 의료진 우선 검토 요청이다. RADIOLOGIST는 우선순위를 수정하고 사유를 감사 로그에 남길 수 있다. 제한적 임상정보는 allowlist 필드만 저장하며 AI 점수를 자동 변경하지 않는다.
