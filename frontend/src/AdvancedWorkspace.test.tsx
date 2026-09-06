import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import App from './App';

afterEach(()=>{cleanup();localStorage.clear();vi.unstubAllGlobals()});
it('shows longitudinal, dataset, monitoring and not-measured safeguards',async()=>{
  localStorage.setItem('ai-literacy-v1.0','accepted');
  vi.stubGlobal('fetch',vi.fn(async(input:string|URL|Request)=>{const url=String(input);const data=url.includes('model-monitoring')?{deployments:[],rule:'검증 데이터 없이는 수치를 생성하지 않습니다.'}:url.includes('regulatory-documents')?[{document_id:'SRS',title:'요구사항 명세서',status:'AUTO_GENERATED_DRAFT',download_url:'/api/v1/regulatory-documents/SRS.md'}]:url.includes('failure-analysis')?{status:'NOT_MEASURED',reason:'승인된 실제 검증 정답 데이터가 없습니다.'}:[];return {ok:true,json:async()=>data} as Response}));
  render(<App/>);fireEvent.click(screen.getByRole('button',{name:'비교·데이터셋·모니터링'}));
  expect(screen.getByText('Longitudinal comparison')).toBeInTheDocument();expect(screen.getByText('데이터셋 구축')).toBeInTheDocument();
  await waitFor(()=>expect(screen.getByText(/승인된 실제 검증 정답 데이터가 없습니다/)).toBeInTheDocument());
  expect(screen.getByText(/AUTO TRAINING OFF/)).toBeInTheDocument();expect(screen.getByRole('link',{name:'Markdown 다운로드'})).toBeInTheDocument();
});
