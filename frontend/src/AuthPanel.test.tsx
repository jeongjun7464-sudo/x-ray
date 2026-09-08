import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AuthPanel from './AuthPanel';

describe('AuthPanel',()=>{
  beforeEach(()=>sessionStorage.clear());
  afterEach(()=>{cleanup();vi.unstubAllGlobals()});
  it('starts an anonymous role session without displaying the token',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({access_token:'sensitive-token',expires_at:Math.floor(Date.now()/1000)+900,role:'QA_RA',subject:'portfolio-user'}),{status:200,headers:{'Content-Type':'application/json'}})));
    render(<AuthPanel/>);fireEvent.change(screen.getByLabelText('데모 역할'),{target:{value:'QA_RA'}});fireEvent.click(screen.getByRole('button',{name:'데모 세션 시작'}));
    await screen.findByText(/QA_RA · 서명 세션/);expect(screen.queryByText('sensitive-token')).not.toBeInTheDocument();expect(screen.getByText(/병원 계정 인증을 대체하지 않습니다/)).toBeInTheDocument();
  });
  it('logs out and removes sessionStorage',async()=>{
    sessionStorage.setItem('xray-demo-session-v1',JSON.stringify({access_token:'hidden',expires_at:Math.floor(Date.now()/1000)+900,role:'REVIEWER'}));vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}',{status:200})));
    render(<AuthPanel/>);fireEvent.click(screen.getByRole('button',{name:'로그아웃'}));await waitFor(()=>expect(sessionStorage.length).toBe(0));expect(screen.getByRole('button',{name:'데모 세션 시작'})).toBeInTheDocument();
  });
  it('shows permission denied separately from login required',async()=>{
    render(<AuthPanel/>);window.dispatchEvent(new CustomEvent('auth:forbidden'));await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('권한 부족'));window.dispatchEvent(new CustomEvent('auth:required'));await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('로그인 필요'));
  });
});
