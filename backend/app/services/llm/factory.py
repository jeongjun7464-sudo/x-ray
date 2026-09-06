from app.core.config import settings
from .dummy_client import DummyLLMClient
from .openai_compatible import OpenAICompatibleClient
from .vllm_client import VLLMClient
def create_llm_client():
    provider=settings.llm_provider.lower()
    if provider=="dummy":return DummyLLMClient(settings.llm_model)
    args=(settings.llm_base_url,settings.llm_model_name,settings.llm_api_key,settings.llm_timeout_seconds,settings.llm_max_retries)
    if provider=="vllm":return VLLMClient(*args)
    if provider=="openai-compatible":return OpenAICompatibleClient(*args)
    raise ValueError("지원하지 않는 LLM_PROVIDER입니다.")
