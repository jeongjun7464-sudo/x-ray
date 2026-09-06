import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import App from './App';

describe('검증·감사 대응 허브',()=>{
 afterEach(()=>cleanup());
 beforeEach(()=>{localStorage.setItem('xray-ai-consent','accepted');vi.stubGlobal('crypto',{randomUUID:()=> 'request-id'});vi.stubGlobal('fetch',vi.fn((input:string|URL,init?:RequestInit)=>{const url=String(input);let body:any=[];if(url.includes('synthetic-safety'))body=[{case:'BLUR'},{case:'WRONG_MODALITY'}];else if(url.includes('annotations/agreement'))body={sample_size:0,region_agreement:null};else if(url.includes('security/status'))body={mime_signature_cross_check:true,zip_path_traversal_blocked:true,malware_scanner:'NOT_CONFIGURED',admin_reauthentication:'INTERFACE_REQUIRED_NOT_CONFIGURED'};else if(url.includes('audit-packages')&&init?.method==='POST')body={package_sha256:'1234567890abcdef'};return Promise.resolve(new Response(JSON.stringify(body),{status:200,headers:{'Content-Type':'application/json'}}))}) as any)});
 it('shows explicit partial statuses and success feedback',async()=>{render(<App/>);fireEvent.click(screen.getByRole('button',{name:'검증·감사 대응'}));expect(screen.getByRole('status')).toHaveTextContent('불러오는 중');await screen.findByText('분석 재현·비교');expect(screen.getAllByText(/INSUFFICIENT_DATA/).length).toBeGreaterThan(0);expect(screen.getByText('NOT_CONFIGURED')).toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:'감사 패키지 생성'}));await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('생성 완료'))});
 it('renders permission denied state',async()=>{vi.stubGlobal('fetch',vi.fn(()=>Promise.resolve(new Response('{}',{status:403}))) as any);render(<App/>);fireEvent.click(screen.getByRole('button',{name:'검증·감사 대응'}));expect(await screen.findByRole('alert')).toHaveTextContent('권한이 없습니다')});
});
