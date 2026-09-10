ALLOWED_STRATEGIES={"MANUAL","SHADOW","CANARY","BLUE_GREEN"}
def deployment_contract(strategy:str,environment:str,traffic_percentage:float)->dict:
    strategy=strategy.upper()
    if strategy not in ALLOWED_STRATEGIES:raise ValueError("unsupported deployment strategy")
    if strategy=="CANARY" and not 0 < traffic_percentage <= 10:raise ValueError("canary traffic must be between 0 and 10 percent")
    external=environment.upper() not in {"LOCAL_DEMO","DEMO","TEST"}
    return {"strategy":strategy,"execution_status":"NOT_CONFIGURED" if external else "LOCAL_DEMO","traffic_percentage":traffic_percentage if strategy=="CANARY" else (0 if strategy=="SHADOW" else 100),"affects_confirmed_result":strategy not in {"SHADOW"},"diagnostic_use":False,"disclaimer":"연구·교육용 보조 결과이며 의료진의 진단과 치료 결정을 대체하지 않습니다."}
