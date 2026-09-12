import {render,screen,fireEvent} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import IntegrationCenter from './IntegrationCenter';
afterEach(()=>vi.unstubAllGlobals());
it('shows empty queue and unconfigured connections',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(input)=>{
    const path=String(input);
    return {ok:true,status:200,json:async()=>path.endsWith('/capabilities')?{external_transmission:'BLOCKED_PENDING_VALIDATION'}:[]};
  }));
  render(<IntegrationCenter baseUrl=""/>);
  expect(await screen.findByText('전송 작업 없음')).toBeInTheDocument();
  expect(screen.getByText(/연결 상태 미측정/)).toBeInTheDocument();
});
it('requires authenticated institution mapping',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:403,json:async()=>({detail:{code:'INSTITUTION_MAPPING_REQUIRED'}})})));
  render(<IntegrationCenter baseUrl=""/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('기관 매핑');
});
it('opens explicit confirmation without transmitting on selection',async()=>{
  const fetchMock=vi.fn(async(input)=>{
    const path=String(input);
    return {ok:true,status:200,json:async()=>path.endsWith('/capabilities')?{}:[{id:'job',destination:'FHIR',status:'AWAITING_CONFIRMATION',attempt_count:0,failure_code:null}]};
  });
  vi.stubGlobal('fetch',fetchMock);
  render(<IntegrationCenter baseUrl=""/>);
  fireEvent.click(await screen.findByText('확인 검토'));
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  expect(screen.getByText('명시적으로 확인')).toBeDisabled();
  expect(fetchMock.mock.calls.some(([path])=>String(path).endsWith('/confirm'))).toBe(false);
});
