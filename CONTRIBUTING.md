# 두 계정 공동 개발 가이드

이 저장소는 `jeongjun7464-sudo`와 `junhaj27-jpg`가 동일한 코드와 절차로 개발할 수 있도록 계정에 종속되지 않게 구성합니다.

## 최초 설정

각 개발자는 자신의 컴퓨터에서 저장소를 복제하고 **자기 계정의 이름과 공개 이메일**을 해당 저장소에만 설정합니다.

```bash
git clone https://github.com/jeongjun7464-sudo/x-ray.git
cd x-ray
git config --local user.name "YOUR_GITHUB_USERNAME"
git config --local user.email "YOUR_GITHUB_NOREPLY_EMAIL"
```

전역 `git config --global`을 바꾸지 않으므로 한 컴퓨터에서 두 계정을 사용해도 다른 프로젝트의 작성자 정보가 섞이지 않습니다. 토큰, 이메일, 환자정보 또는 실제 DICOM은 커밋하지 않습니다.

## 권장 작업 흐름

```bash
git switch main
git pull --ff-only origin main
git switch -c feat/short-description
# 코드와 테스트 수정
git add <변경한 파일>
git commit -m "feat: describe the change"
git push -u origin feat/short-description
```

그다음 GitHub에서 `main` 대상 Pull Request를 만들고 다른 계정의 검토를 받습니다. `main` 직접 푸시는 긴급한 문서 수정 외에는 피합니다.

## 권한에 따른 두 가지 방식

- Collaborator 권한이 있는 계정: 위 예시처럼 원본 저장소에 브랜치를 푸시합니다.
- Collaborator 권한이 없는 계정: 저장소를 Fork한 뒤 자기 Fork에 브랜치를 푸시하고 원본 저장소로 Pull Request를 보냅니다.

`CODEOWNERS`는 두 계정을 리뷰어로 연결하지만 쓰기 권한을 만들지는 않습니다. 저장소 소유자가 GitHub의 **Settings → Collaborators**에서 `junhaj27-jpg`를 추가해야 원본 저장소에 직접 브랜치를 푸시할 수 있습니다.

## 병합 전 확인

```bash
PYTHONPATH=backend:ml pytest backend/tests ml/tests -q
cd frontend
pnpm test -- --run
pnpm build
```

- 더미 모델은 `DEMO / DUMMY`로 표시합니다.
- 실제로 측정하지 않은 임상 성능을 작성하지 않습니다.
- 낮은 신뢰도, OOD, UNKNOWN, 메타데이터 충돌과 신고 결과는 사람 검토를 유지합니다.
- 새 요구사항은 `docs/traceability-matrix.md`에 위험과 테스트를 연결합니다.
