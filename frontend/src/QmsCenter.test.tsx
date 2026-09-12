import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import QmsCenter from './QmsCenter';
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body});
it('shows measured counts separately from not measured and release block',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response({requirements:0,clinical_performance:'NOT_MEASURED',release_block:true})));
 render(<QmsCenter baseUrl=""/>);
 expect(await screen.findByText('NOT_MEASURED')).toBeInTheDocument();
 expect(screen.getByText('배포 차단')).toBeInTheDocument();
 expect(screen.getByText(/법적 전자서명/)).toBeInTheDocument();
});
it('shows permission denied with login remedy',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response({detail:{code:'AUTHORIZATION_DENIED'}},403)));
 render(<QmsCenter baseUrl=""/>);
 expect(await screen.findByText(/서명 세션으로 로그인/)).toBeInTheDocument();
});
it('loads empty requirements and submits actual API request',async()=>{
 const fetch=vi.fn(async(_input:unknown,init?:RequestInit)=>response(init?.method==='POST'?{id:'req-1'}:[]));vi.stubGlobal('fetch',fetch);
 render(<QmsCenter baseUrl=""/>);
 fireEvent.click(screen.getByRole('button',{name:'요구사항'}));
 expect(await screen.findByText('등록된 자료가 없습니다.')).toBeInTheDocument();
 fireEvent.change(screen.getByLabelText('등록 내용'),{target:{value:JSON.stringify({requirement_id:'REQ-1'})}});
 fireEvent.click(screen.getByRole('button',{name:'서버에 저장'}));
 await waitFor(()=>expect(fetch.mock.calls.some(([url,init])=>String(url).endsWith('/qms/requirements')&&init?.method==='POST')).toBe(true));
});
it('shows integrity failed state',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response({detail:{code:'AUDIT_INTEGRITY_FAILED'}},409)));
 render(<QmsCenter baseUrl=""/>);
 expect(await screen.findByText(/무결성 검사 실패/)).toBeInTheDocument();
});
it('shows loading and network error without claiming success',async()=>{
 let reject:(reason:Error)=>void=()=>{};
 vi.stubGlobal('fetch',vi.fn(()=>new Promise((_resolve,rejectPromise)=>{reject=rejectPromise})));
 render(<QmsCenter baseUrl=""/>);
 expect(screen.getByRole('status')).toHaveTextContent('불러오는 중');
 reject(new Error('offline'));
 expect(await screen.findByText(/연결을 확인한 뒤 새로고침/)).toBeInTheDocument();
});
