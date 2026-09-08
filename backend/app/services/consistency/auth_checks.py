from app.core.auth import validate_secret,AuthenticationError
from app.core.config import settings
from .base import ConsistencyRule
from .registry import register
def production():return settings.environment.lower() in {"production","prod"}
@register
class AuthEnforcedRule(ConsistencyRule):
    rule_id="AUTH-001";category="AUTH_SECURITY";severity="CRITICAL"
    def check(self,c):
        ok=not production() or settings.auth_enforced;return self.finding("PASS" if ok else "FAIL","운영 환경 인증 강제 여부",True,settings.auth_enforced,[{"source_type":"CONFIG","field":"auth_enforced"}],"RELEASE_BLOCK" if not ok else "NONE",not ok)
@register
class AuthSecretRule(ConsistencyRule):
    rule_id="AUTH-002";category="AUTH_SECURITY";severity="CRITICAL"
    def check(self,c):
        try:validate_secret(settings.auth_session_secret,reject_example=production());safe=True
        except AuthenticationError:safe=False
        ok=not (production() or settings.auth_enforced) or safe;return self.finding("PASS" if ok else "FAIL","서명키 설정 여부를 비밀값 노출 없이 확인했습니다.","안전한 외부 주입 키","CONFIGURED" if safe else "EMPTY_SHORT_OR_EXAMPLE",[{"source_type":"CONFIG","field":"auth_session_secret","value":"REDACTED"}],"STARTUP_BLOCK" if not ok and settings.auth_enforced else "RELEASE_BLOCK" if not ok else "NONE",not ok)
@register
class DemoTokenProductionRule(ConsistencyRule):
    rule_id="AUTH-003";category="AUTH_SECURITY";severity="HIGH"
    def check(self,c):
        ok=not production() or not settings.auth_demo_tokens_enabled;return self.finding("PASS" if ok else "FAIL","운영 환경 데모 토큰 비활성화 여부",False,settings.auth_demo_tokens_enabled,action="RELEASE_BLOCK" if not ok else "NONE",review=not ok)
@register
class LegacyHeaderProductionRule(ConsistencyRule):
    rule_id="AUTH-004";category="AUTH_SECURITY";severity="CRITICAL"
    def check(self,c):
        ok=not production() or not settings.auth_allow_legacy_headers;return self.finding("PASS" if ok else "FAIL","운영 환경 legacy X-Role 비활성화 여부",False,settings.auth_allow_legacy_headers,action="RELEASE_BLOCK" if not ok else "NONE",review=not ok)
@register
class SessionTTLRule(ConsistencyRule):
    rule_id="AUTH-005";category="AUTH_SECURITY";severity="HIGH"
    def check(self,c):
        ok=60<=settings.auth_session_ttl_seconds<=3600;return self.finding("PASS" if ok else "FAIL","세션 TTL 범위 준수 여부","60..3600",settings.auth_session_ttl_seconds,action="CONFIGURATION_CHANGE_REQUIRED" if not ok else "NONE",review=not ok)
@register
class PublicPathRule(ConsistencyRule):
    rule_id="AUTH-006";category="AUTH_SECURITY";severity="MEDIUM"
    def check(self,c):
        paths=[x for x in settings.auth_public_paths.split(",") if x.strip()];broad=any(x.strip() in {"/","/api","/api/"} for x in paths);return self.finding("FAIL" if broad else "PASS","공개 경로 최소화 여부","명시적 경로",paths,action="QA_RA_REVIEW" if broad else "NONE",review=broad)
@register
class SecurityEventSecretRule(ConsistencyRule):
    rule_id="AUTH-007";category="AUTH_SECURITY";severity="HIGH"
    def check(self,c):
        events=c.get("security_events")
        if events is None:return self.finding("NOT_VERIFIABLE","보안 이벤트 payload가 제공되지 않았습니다.")
        leaked=any(any(k in str(e).lower() for k in ("access_token","authorization","signature","auth_session_secret")) for e in events);return self.finding("FAIL" if leaked else "PASS","보안 이벤트 토큰 원문 미포함 여부","민감 필드 없음","LEAK_DETECTED" if leaked else "clean",action="RELEASE_BLOCK" if leaked else "NONE",review=leaked)
@register
class AuthenticationStatusSemanticsRule(ConsistencyRule):
    rule_id="AUTH-008";category="AUTH_SECURITY";severity="HIGH"
    def check(self,c):
        evidence=c.get("authentication_test_results")
        if evidence is None:return self.finding("NOT_VERIFIABLE","401/403 구분 시험 결과가 제공되지 않았습니다.",evidence=[{"source_type":"TEST","field":"authentication_test_results"}])
        ok=evidence.get("missing_or_invalid_token")==401 and evidence.get("authenticated_insufficient_role")==403
        return self.finding("PASS" if ok else "FAIL","인증 실패 401과 권한 부족 403 구분 여부",{"missing_or_invalid_token":401,"authenticated_insufficient_role":403},evidence,action="RELEASE_BLOCK" if not ok else "NONE",review=not ok)
