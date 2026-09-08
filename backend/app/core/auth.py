from __future__ import annotations
import base64,hashlib,hmac,json,re,secrets,time
from contextvars import ContextVar
from dataclasses import asdict,dataclass

ALLOWED_ROLES={"USER","TECHNICIAN","LABELER","RADIOLOGIST","ADJUDICATOR","ML_ENGINEER","QA_RA","ADMIN","REVIEWER"}
TOKEN_VERSION=1;MIN_TTL_SECONDS=60;MAX_TTL_SECONDS=3600;MAX_CLOCK_SKEW_SECONDS=30
class AuthenticationError(ValueError):
    def __init__(self,code="INVALID_SESSION"):super().__init__("인증 세션이 유효하지 않습니다.");self.code=code
@dataclass(frozen=True)
class Principal:
    subject:str;role:str;issued_at:int;expires_at:int;authentication_method:str="SIGNED_SESSION"
_principal:ContextVar[Principal|None]=ContextVar("authenticated_principal",default=None)
def set_current_principal(value):return _principal.set(value)
def reset_current_principal(token):_principal.reset(token)
def current_principal():return _principal.get()
def get_current_principal():
    principal=current_principal()
    if principal is None:raise AuthenticationError("MISSING_AUTHENTICATED_PRINCIPAL")
    return principal
def _b64(data:bytes)->str:return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
def _decode(value:str)->bytes:
    try:return base64.urlsafe_b64decode(value+"="*(-len(value)%4))
    except Exception as exc:raise AuthenticationError("MALFORMED_TOKEN") from exc
def validate_secret(secret:str,reject_example:bool=False):
    normalized=(secret or "").strip().lower()
    unsafe=normalized in {"changeme","change-me","example","example-secret","secret","your-secret-here"} or len(set(normalized))<8
    if not secret or len(secret)<32 or (reject_example and unsafe):raise AuthenticationError("AUTH_SECRET_NOT_CONFIGURED")
def issue_session_token(subject:str,role:str,secret:str,ttl_seconds:int=900,now:int|None=None)->tuple[str,Principal]:
    validate_secret(secret);role=role.upper();now=int(time.time() if now is None else now)
    if role not in ALLOWED_ROLES:raise AuthenticationError("ROLE_NOT_ALLOWED")
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,64}",subject):raise AuthenticationError("INVALID_SUBJECT")
    ttl=max(MIN_TTL_SECONDS,min(int(ttl_seconds),MAX_TTL_SECONDS));payload={"v":TOKEN_VERSION,"sub":subject,"role":role,"iat":now,"exp":now+ttl,"jti":secrets.token_urlsafe(12)};encoded=_b64(json.dumps(payload,separators=(",",":"),sort_keys=True).encode());signature=_b64(hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).digest());return encoded+"."+signature,Principal(subject,role,payload["iat"],payload["exp"])
def verify_session_token(token:str,secret:str,now:int|None=None)->Principal:
    validate_secret(secret);now=int(time.time() if now is None else now)
    try:encoded,provided=token.split(".",1);expected=_b64(hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).digest())
    except ValueError as exc:raise AuthenticationError("MALFORMED_TOKEN") from exc
    if not hmac.compare_digest(provided,expected):raise AuthenticationError("INVALID_SIGNATURE")
    try:data=json.loads(_decode(encoded))
    except Exception as exc:raise AuthenticationError("MALFORMED_TOKEN") from exc
    if data.get("v")!=TOKEN_VERSION:raise AuthenticationError("UNSUPPORTED_TOKEN_VERSION")
    if data.get("role") not in ALLOWED_ROLES:raise AuthenticationError("ROLE_NOT_ALLOWED")
    if not isinstance(data.get("iat"),int) or data["iat"]>now+MAX_CLOCK_SKEW_SECONDS:raise AuthenticationError("FUTURE_ISSUED_TOKEN")
    if not isinstance(data.get("exp"),int) or data["exp"]<=now:raise AuthenticationError("SESSION_EXPIRED")
    duration=data["exp"]-data["iat"]
    if duration<MIN_TTL_SECONDS or duration>MAX_TTL_SECONDS:raise AuthenticationError("TTL_OUT_OF_RANGE")
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,64}",str(data.get("sub",""))):raise AuthenticationError("INVALID_SUBJECT")
    return Principal(data["sub"],data["role"],data["iat"],data["exp"])
def extract_bearer_token(authorization:str|None)->str:
    if not authorization:raise AuthenticationError("MISSING_BEARER_TOKEN")
    parts=authorization.split()
    if len(parts)!=2 or parts[0].lower()!="bearer" or not parts[1]:raise AuthenticationError("INVALID_AUTHORIZATION_FORMAT")
    return parts[1]
def principal_dict(principal:Principal):return asdict(principal)
