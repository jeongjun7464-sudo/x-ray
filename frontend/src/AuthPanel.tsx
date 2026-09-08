import { useEffect, useState } from 'react';
import { getSession, loginWithDemoSession, logout, type Session } from './api';

const ROLES=['TECHNICIAN','LABELER','RADIOLOGIST','ADJUDICATOR','ML_ENGINEER','QA_RA','ADMIN','REVIEWER'];

export default function AuthPanel({baseUrl=''}:{baseUrl?:string}){
  const [session,setCurrent]=useState<Session|null>(()=>getSession());
  const [anonymousId,setAnonymousId]=useState('portfolio-user');
  const [role,setRole]=useState('REVIEWER');
  const [state,setState]=useState<'ready'|'login-required'|'permission-denied'>('ready');
  const [message,setMessage]=useState('');
  useEffect(()=>{const changed=()=>setCurrent(getSession()),required=()=>{setState('login-required');setMessage('세션이 없거나 만료되었습니다. 다시 로그인하세요.')},forbidden=()=>{setState('permission-denied');setMessage('로그인되어 있지만 이 작업을 수행할 역할 권한이 없습니다.')};window.addEventListener('auth:changed',changed);window.addEventListener('auth:required',required);window.addEventListener('auth:forbidden',forbidden);return()=>{window.removeEventListener('auth:changed',changed);window.removeEventListener('auth:required',required);window.removeEventListener('auth:forbidden',forbidden)}},[]);
  const login=async()=>{setMessage('');try{const next=await loginWithDemoSession(baseUrl,anonymousId,role);setCurrent(next);setState('ready')}catch(error){const problem=error as {status?:number};setMessage(problem.status===503?'데모 서명키가 설정되지 않았습니다. 개발 환경 설정을 확인하세요.':'데모 세션을 시작하지 못했습니다. 익명 ID와 역할을 확인하세요.')}};
  const signOut=async()=>{await logout(baseUrl).catch(()=>undefined);setCurrent(null);setState('login-required');setMessage('토큰을 브라우저에서 폐기했습니다. 중앙 차단 목록은 NOT_CONFIGURED입니다.')};
  return <section aria-label="인증 상태" aria-live="polite" style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',justifyContent:'flex-end'}}>
    <span className="status"><i/>DEMO · DUMMY 모델</span>
    {session?<><span className="status">{session.role} · 서명 세션</span><time dateTime={new Date(session.expires_at*1000).toISOString()} style={{fontSize:12}}>만료 {new Date(session.expires_at*1000).toLocaleTimeString()}</time><button className="review-btn" onClick={signOut}>로그아웃</button></>:<><label style={{fontSize:12}}>익명 사용자 ID <input aria-label="익명 사용자 ID" value={anonymousId} pattern="[A-Za-z0-9._-]{3,64}" onChange={e=>setAnonymousId(e.target.value)}/></label><label style={{fontSize:12}}>데모 역할 <select aria-label="데모 역할" value={role} onChange={e=>setRole(e.target.value)}>{ROLES.map(x=><option key={x}>{x}</option>)}</select></label><button className="review-btn" onClick={login}>데모 세션 시작</button></>}
    <small style={{width:'100%'}}>이 로그인은 연구·교육용 데모 세션이며 병원 계정 인증을 대체하지 않습니다.</small>
    {message&&<small role="status" data-auth-state={state} style={{width:'100%',color:'#b45309'}}>{state==='permission-denied'?'권한 부족: ':state==='login-required'?'로그인 필요: ':''}{message}</small>}
  </section>;
}
