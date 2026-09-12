"""Deterministic draft generator, independent from validation. No sLLM call implied."""
from app.services.qms_integrity import canonical

DISCLAIMER = 'DRAFT — 연구·교육용 품질관리 초안. QA/RA 검토·승인이 필요하며 규제 적합성 또는 법적 전자서명을 보장하지 않습니다.'

def generate_draft(document_type, title, sources):
    return '\n\n'.join([DISCLAIMER, '# ' + title, '문서 유형: ' + document_type,
        '## 근거\n' + (canonical(sources) if sources else 'NO_EVIDENCE'),
        '## 요구사항·위험·시험\nHUMAN_INPUT_REQUIRED',
        '## 측정 결과\nNOT_MEASURED — 근거 없는 성능을 생성하지 않음',
        '## 제한사항\nNOT_VERIFIABLE — 독립 검토 필요'])
