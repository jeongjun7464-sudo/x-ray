from .base import ConsistencyRule
from .registry import register

LABELS = [
    '승인 요구사항 시험 연결','안전 요구사항 위험 연결','위험통제 검증시험','실패 시험 결함 연결',
    '중대 결함 CAPA 연결','변경 영향평가','회귀시험','승인 버전 일치','문서 해시 일치',
    '작성자 승인자 분리','승인 의미 사유','재인증','대체 문서 비발효','모델 변경 위험 연결',
    '데이터셋 변경 공정성 검증','연동 변경 통합시험','CRITICAL 통제','패키지 무결성',
    '추적성 대상 존재','미측정 성능 PASS 금지']

def build(number,label):
    def check(self,context):
        value=context.get('qms',{}).get(self.rule_id)
        return self.finding('NOT_VERIFIABLE' if value is None else 'PASS' if value is True else 'FAIL',
            label,True,value,action='NONE' if value is True else 'APPROVAL_BLOCK',review=value is not True)
    return type(f'QMS_{number:03}',(ConsistencyRule,),{'rule_id':f'QMS-{number:03}',
        'category':'QMS','severity':'CRITICAL' if number in {8,9,10,12,17,18,20} else 'HIGH','check':check})

for number,label in enumerate(LABELS,1): register(build(number,label))
