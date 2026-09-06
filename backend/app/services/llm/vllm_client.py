from .openai_compatible import OpenAICompatibleClient
class VLLMClient(OpenAICompatibleClient):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs,provider="vllm")
