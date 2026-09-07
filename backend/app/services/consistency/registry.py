RULES=[]
def register(cls):RULES.append(cls());return cls
def catalog():return [{"rule_id":r.rule_id,"version":r.version,"category":r.category,"severity":r.severity,"name":r.__class__.__name__} for r in RULES]
