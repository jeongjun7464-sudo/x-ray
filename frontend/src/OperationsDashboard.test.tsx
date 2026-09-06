import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import App from './App';
afterEach(()=>{cleanup();localStorage.clear();vi.unstubAllGlobals()});
it('shows PACS status, release gate, monitoring and CAPA workflow',async()=>{
  localStorage.setItem('ai-literacy-v1.0','accepted');
  vi.stubGlobal('fetch',vi.fn(async(input:string|URL|Request)=>{const url=String(input);const data=url.includes('/monitoring/metrics')?{total_analyses:0,analysis_success_rate:null,average_processing_ms:null,p95_processing_ms:null,quality_reject_rate:null,ood_rate:null,clinical_review_rate:null,services:{database:'UP',queue:'LOCAL_ONLY'},unmeasured_note:'자료가 없는 지표는 null'}:url.includes('/integrations/status')?{pacs:'NOT_CONFIGURED',external_transmission:'DISABLED_BY_DEFAULT'}:[];return {ok:true,json:async()=>data} as Response}));
  render(<App/>);fireEvent.click(screen.getByRole('button',{name:'의료기관 운영'}));
  expect(screen.getByText('PACS·서비스 연동 상태')).toBeInTheDocument();expect(screen.getByText('Model Release Gate')).toBeInTheDocument();expect(screen.getByText('반복 오류와 CAPA')).toBeInTheDocument();
  await waitFor(()=>expect(screen.getByText('NOT_CONFIGURED')).toBeInTheDocument());expect(screen.getAllByText(/NOT_MEASURED/).length).toBeGreaterThan(0);
});
