import '@testing-library/jest-dom/vitest';
import {render,screen,waitFor,fireEvent} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import ModelOpsCenter from './ModelOpsCenter';
afterEach(()=>vi.restoreAllMocks());
describe('ModelOpsCenter',()=>{
 it('shows loading then empty',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>[]}));render(<ModelOpsCenter baseUrl=""/>);expect(screen.getByRole('status')).toHaveTextContent('불러오는 중');expect(await screen.findByText('등록된 모델 릴리스가 없습니다')).toBeInTheDocument()});
 it('shows permission and error states',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:403}));const {unmount}=render(<ModelOpsCenter baseUrl=""/>);expect(await screen.findByText('ModelOps 조회 권한이 없습니다.')).toBeInTheDocument();unmount();vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new Error()));render(<ModelOpsCenter baseUrl=""/>);expect(await screen.findByText('ModelOps 데이터를 불러오지 못했습니다.')).toBeInTheDocument()});
 it('shows release detail, NOT_MEASURED and role-gated actions',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>[{model_release_id:'r1',name:'candidate',version:'1.0',status:'VALIDATION_FAILED',checkpoint_sha256:'a'.repeat(64),training_dataset_version:'train-1',test_dataset_version:'test-1',registered_by:'engineer',specification:{intended_use:'research',prohibited_use:'diagnosis'}}]}));render(<ModelOpsCenter baseUrl=""/>);await waitFor(()=>expect(screen.getByText('candidate')).toBeInTheDocument());fireEvent.click(screen.getByText('상세'));expect(screen.getByText(/NOT_MEASURED/)).toBeInTheDocument();expect(screen.getByText('승인 검토')).toBeDisabled();expect(screen.getByText('DEMO 배포')).toBeDisabled();expect(screen.getByLabelText('롤백 확인')).toBeDisabled()});
});
