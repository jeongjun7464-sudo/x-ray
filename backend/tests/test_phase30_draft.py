import pytest
from fastapi import HTTPException
from app.core.auth import Principal
from app.services.electronic_approval import require_electronic_approval
from app.services.qms_validation import ambiguity, validate_text

def test_qms_ambiguous_requirement_needs_human_review():
    assert ambiguity('가능하면 빠르게 분석한다')
    assert not ambiguity('응답시간을 ms 단위로 저장한다')

@pytest.mark.parametrize('text', ['환자명: SYNTHETIC', 'NOT_MEASURED PASS', '법적 전자서명 충족'])
def test_qms_unsafe_draft_content_blocked(text):
    with pytest.raises(HTTPException) as error: validate_text(text)
    assert error.value.status_code == 422

def test_qms_approval_fail_closed_and_separation():
    principal = Principal('reviewer', 'QA_RA', 1, 100)
    with pytest.raises(HTTPException) as error:
        require_electronic_approval(principal, 'author', 1, 1, 'APPROVED', 'Independent review')
    assert error.value.detail['code'] == 'REAUTHENTICATION_NOT_CONFIGURED'
    with pytest.raises(HTTPException) as error:
        require_electronic_approval(principal, 'reviewer', 1, 1, 'APPROVED', 'Independent review')
    assert error.value.detail['code'] == 'SEPARATION_OF_DUTIES_REQUIRED'

def test_qms_generator_no_evidence_never_calls_llm(monkeypatch):
    from app.core.config import settings
    from app.services.qms_agent import generate_qms_draft
    monkeypatch.setattr(settings,'qms_sllm_enabled',True)
    class Retriever:
        def search(self,*args): return {'mode':'LOCAL_FALLBACK','results':[]}
    class Client:
        def generate(self,*args): raise AssertionError('No evidence must not call LLM')
    result=generate_qms_draft('TEST_REPORT','Synthetic draft','QA_RA','A',retriever=Retriever(),client=Client())
    assert result['mode']=='NO_EVIDENCE' and 'NO_EVIDENCE' in result['content']

def test_qms_generator_rejects_unsupported_citations(monkeypatch):
    from types import SimpleNamespace
    from app.core.config import settings
    from app.services.qms_agent import generate_qms_draft
    monkeypatch.setattr(settings,'qms_sllm_enabled',True)
    class Retriever:
        def search(self,*args): return {'mode':'MOCK','results':[{'chunk_id':'known','text':'Synthetic evidence',
            'approval_status':'APPROVED','allowed_roles':['QA_RA'],'institution_id':'A'}]}
    class Client:
        def generate(self,*args): return SimpleNamespace(dummy_mode=False,content='{"sections":[{"heading":"Test","text":"Unsupported","citations":["invented"]}]}')
    with pytest.raises(HTTPException) as error:
        generate_qms_draft('TEST_REPORT','Synthetic draft','QA_RA','A',retriever=Retriever(),client=Client())
    assert error.value.detail['code']=='QMS_DRAFT_GENERATION_UNVERIFIABLE'
