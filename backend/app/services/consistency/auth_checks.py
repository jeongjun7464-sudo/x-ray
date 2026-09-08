from app.core.config import settings
from .base import ConsistencyRule
from .registry import register
def production():return settings.environment.lower() in {"production","prod"}
@register
class AuthEnforcedRule(ConsistencyRule):
    rule_id="AUTH-001";category="AUTH_SECURITY";severity="CRITICAL"
    def check(self,c):
        ok=not production() or settings.auth_enforced;return self.finding("PASS" if ok else "FAIL","운영 환경 인증 강제 여부",True,settings.auth_enforced,[{"source_type":"CONFIG","field":"auth_enforced"}],"BLOCK_MODEL_DEPLOYMENT" if not ok else "NONE",not ok)
@register
class AuthSecretRule(ConsistencyRule):
    rule_id="AUTH-002";category="AUTH_SECURITY";severity="CRITICAL"
    def check(self,c):
        ok=not (production() or settings.auth_enforced) or len(settings.auth_session_secret)>=32;return self.finding("PASS" if ok else "FAIL","서명키 설정 여부를 길이만으로 확인했습니다.","32자 이상","CONFIGURED" if len(settings.auth_session_secret)>=32 else "EMPTY_OR_SHORT",[{"source_type":"CONFIG","field":"auth_session_secret","value":"REDACTED"}],"BLOCK_MODEL_DEPLOYMENT" if not ok else "NONE",not ok)
@register
class DemoTokenProductionRule(ConsistencyRule):
    rule_id="AUTH-003";category="AUTH_SECURITY";severity="HIGH"
    def check(self,c):
        ok=not production() or not settings.auth_demo_tokens_enabled;return self.finding("PASS" if ok else "FAIL","운영 환경 데모 토큰 비활성화 여부",False,settings.auth_demo_tokens_enabled,action="BLOCK_MODEL_DEPLOYMENT" if not ok else "NONE",review=not ok)
@register
class LegacyHeaderProductionRule(ConsistencyRule):
    rule_id="AUTH-004";category="AUTH_SECURITY";severity="CRITICAL"
    def check(self,c):
        ok=not production() or not settings.auth_allow_legacy_headers;return self.finding("PASS" if ok else "FAIL","운영 환경 legacy X-Role 비활성화 여부",False,settings.auth_allow_legacy_headers,action="BLOCK_MODEL_DEPLOYMENT" if not ok else "NONE",review=not ok)
@register
class SessionTTLRule(ConsistencyRule):
    rule_id="AUTH-005";category="AUTH_SECURITY";severity="HIGH"
    def check(self,c):
        ok=0<settings.auth_session_ttl_seconds<=3600;return self.finding("PASS" if ok else "FAIL","세션 TTL 최대 1시간 준수 여부","1..3600",settings.auth_session_ttl_seconds,action="BLOCK_AUTO_APPROVAL" if not ok else "NONE",review=not ok)
@register
class PublicPathRule(ConsistencyRule):
    rule_id="AUTH-006";category="AUTH_SECURITY";severity="MEDIUM"
    def check(self,c):
        paths=[x for x in settings.auth_public_paths.split(",") if x.strip()];broad=any(x.strip() in {"/","/api","/api/"} for x in paths);return self.finding("FAIL" if broad else "PASS","공개 경로 최소화 여부","명시적 경로",paths,action="BLOCK_AUTO_APPROVAL" if broad else "NONE",review=broad)
@register
class SecurityEventSecretRule(ConsistencyRule):
    rule_id="AUTH-007";category="AUTH_SECURITY";severity="HIGH"
    def check(self,c):
        events=c.get("security_events")
        if events is None:return self.finding("NOT_VERIFIABLE","보안 이벤트 payload가 제공되지 않았습니다.")
        leaked=any(any(k in str(e).lower() for k in ("access_token","authorization","signature","auth_session_secret")) for e in events);return self.finding("FAIL" if leaked else "PASS","보안 이벤트 토큰 원문 미포함 여부","민감 필드 없음","LEAK_DETECTED" if leaked else "clean",action="BLOCK_MODEL_DEPLOYMENT" if leaked else "NONE",review=leaked)
