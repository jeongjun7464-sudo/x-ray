class FindingGradCAM:
    def __init__(self,model=None,dummy_mode:bool=True):self.model=model;self.dummy_mode=dummy_mode
    @property
    def available(self)->bool:return not self.dummy_mode and self.model is not None
    def generate(self,*_):
        if not self.available:raise RuntimeError("DUMMY 모델은 실제 Grad-CAM을 제공하지 않습니다.")
        raise NotImplementedError("승인된 체크포인트의 target layer를 설정해야 합니다.")
