import {useEffect, useState} from 'react';
import {apiFetch} from './api';

type Job = {id:string; destination:string; status:string; attempt_count:number; failure_code:string|null};
export default function IntegrationCenter({baseUrl}:{baseUrl:string}) {
  const [state,setState] = useState('loading');
  const [jobs,setJobs] = useState<Job[]>([]);
  const [connections,setConnections] = useState<Record<string,unknown>[]>([]);
  const [message,setMessage] = useState('');
  const [analysis,setAnalysis] = useState('');
  const [preview,setPreview] = useState<Record<string,unknown>|null>(null);
  const [selected,setSelected] = useState<Job|null>(null);
  const [reason,setReason] = useState('');
  const [busy,setBusy] = useState(false);
  const request = async(path:string, init?:RequestInit) => {
    const response = await apiFetch(baseUrl + '/api/v1' + path, init);
    const data = await response.json();
    if(!response.ok) {
      if(response.status === 401 || response.status === 403) setState('permission');
      throw new Error(data.detail?.code || data.reason_codes?.join(', ') || '요청 실패');
    }
    return data;
  };
  const load = async() => {
    setState('loading');
    try {
      const [list, caps] = await Promise.all([request('/external-transfers'),request('/integrations/capabilities')]);
      setJobs(list); setMessage(caps.external_transmission); setState('success');
    } catch(e) {
      setState(previous=>previous==='permission'?'permission':'error');
      setMessage(e instanceof Error?e.message:'요청 실패');
    }
  };
  useEffect(()=>{void load()},[]);
  const perform = async(action:()=>Promise<void>) => {
    setBusy(true);
    try {await action()} catch(e) {setMessage(e instanceof Error?e.message:'요청 실패')}
    finally {setBusy(false)}
  };
  if(state==='loading') return <div className="card" role="status">의료기관 연동 정보를 불러오는 중입니다.</div>;
  if(state==='permission') return <div className="card" role="alert">권한 또는 승인된 기관 매핑이 필요합니다. 로그인과 기관 설정을 확인하세요.<button onClick={load}>다시 확인</button></div>;
  if(state==='error') return <div className="card" role="alert">{message}<button onClick={load}>다시 시도</button></div>;
  return <div className="literacy">
    <section className="card"><h2>의료기관 연동센터</h2><p>연구용 연동입니다. 실제 병원 연결은 설정 후 확인해야 합니다. 전송은 검증 완료 전까지 차단됩니다.</p>
      <p role="status">{message}</p>
      <button disabled={busy} onClick={()=>perform(async()=>{
        const result=await request('/integrations/health-check',{method:'POST'});
        setConnections(Object.entries(result).map(([provider,value])=>({provider,...value as object})));
      })}>연결 상태 확인</button>
      {connections.length===0?<p>연결 상태 미측정 · NOT_CONFIGURED</p>:<table aria-label="연결 상태"><thead><tr><th>연동</th><th>상태</th><th>사유</th></tr></thead><tbody>{connections.map(row=><tr key={String(row.provider)}><td>{String(row.provider)}</td><td>{String(row.status)}</td><td>{String(row.code||'-')}</td></tr>)}</tbody></table>}
    </section>
    <section className="card"><h3>합성 Study 검색</h3><button disabled={busy} onClick={()=>perform(async()=>{
      const result=await request('/dicomweb/studies/search',{method:'POST',body:JSON.stringify({Modality:'DX',limit:25})});
      setMessage(result.status==='CONNECTED'?(result.data.length?JSON.stringify(result.data):'검색 결과 없음'):result.code);
    })}>DX Study 검색</button><p>결과는 UID 해시로만 표시합니다. 가져오기 매핑은 아직 연결되지 않았습니다.</p></section>
    <section className="card"><h3>FHIR 미리보기</h3><label>익명 분석 ID<input aria-label="익명 분석 ID" value={analysis} onChange={e=>setAnalysis(e.target.value)}/></label>
      <button disabled={busy||!analysis} onClick={()=>perform(async()=>setPreview(await request('/xray/analyses/'+encodeURIComponent(analysis)+'/fhir')))}>미리보기</button>
      {preview&&<><p>전체 표준 적합성: NOT_VERIFIED · 전송 불가</p><pre style={{overflowX:'auto',maxHeight:320}}>{JSON.stringify(preview,null,2)}</pre>
        <button disabled={busy} onClick={()=>perform(async()=>{
          await request('/external-transfers/proposals',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({analysis_id:analysis,destination:'FHIR',reason:'연구용 결과 전송 검토 제안'})});
          await load();
        })}>전송 제안 생성</button></>}
    </section>
    <section className="card"><h3>전송 대기열</h3>{jobs.length===0?<p>전송 작업 없음</p>:<table aria-label="전송 대기열"><thead><tr><th>대상</th><th>상태</th><th>시도 횟수</th><th>오류</th><th>작업</th></tr></thead><tbody>{jobs.map(job=><tr key={job.id}><td>{job.destination}</td><td>{job.status}</td><td>{job.attempt_count}</td><td>{job.failure_code||'-'}</td><td><button disabled={busy||job.status!=='AWAITING_CONFIRMATION'} onClick={()=>{setSelected(job);setReason('')}}>확인 검토</button></td></tr>)}</tbody></table>}</section>
    {selected&&<div role="dialog" aria-modal="true" aria-labelledby="transfer-title" className="card"><h3 id="transfer-title">외부 전송 확인</h3><p>확인 후에도 서버 검증이 실패하면 전송되지 않습니다.</p><label>전송 사유<input aria-label="전송 사유" value={reason} onChange={e=>setReason(e.target.value)}/></label><button disabled={busy||reason.trim().length<3} onClick={()=>perform(async()=>{
      try {await request('/external-transfers/'+selected.id+'/confirm',{method:'POST',body:JSON.stringify({confirmed:true,reason})});setMessage('확인 처리됨')}
      finally {setSelected(null);setJobs(await request('/external-transfers'))}
    })}>명시적으로 확인</button><button disabled={busy} onClick={()=>setSelected(null)}>닫기</button></div>}
  </div>;
}
