import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import App from './App';

afterEach(()=>{cleanup();localStorage.clear();vi.unstubAllGlobals()});
describe('integrated xray analysis',()=>{
  it('renders accessible integrated upload and loading controls',async()=>{
    localStorage.setItem('ai-literacy-v1.0','accepted');
    const result={analysis_id:'demo',quality:{status:'WARNING',score:.7},anatomical_region:{display_name:'흉부',confidence:.8},screening:{status:'ABNORMALITY_SUSPECTED'},findings:[{code:'LUNG_OPACITY',display_name:'폐 음영 증가',probability:.78,threshold:.5,positive:true}],explanation:{available:false},routing:{review_required:true,priority:'MEDIUM',reasons:['ABNORMALITY_SUSPECTED']},model:{region_model_version:'dummy-v1',finding_model_version:'dummy-finding-v1',dummy_mode:true}};
    vi.stubGlobal('fetch',vi.fn(async(input:string|URL|Request)=>({ok:true,json:async()=>String(input).includes('/api/predictions')?[]:result})));
    vi.stubGlobal('URL',{...URL,createObjectURL:()=>"blob:synthetic"});
    render(<App/>);fireEvent.click(screen.getByRole('button',{name:'통합 X-ray 분석'}));
    const input=screen.getByLabelText(/PNG, JPG 또는 DICOM 선택/,{selector:'input'});const start=screen.getByRole('button',{name:'통합 분석 시작'});expect(start).toBeDisabled();fireEvent.change(input,{target:{files:[new File(['x'],'x.png',{type:'image/png'})]}});await waitFor(()=>expect(start).toBeEnabled());expect(screen.getByText('x.png')).toBeInTheDocument();expect(screen.getByText(/파일 검증 → 비식별화/)).toBeInTheDocument();
  });
});
