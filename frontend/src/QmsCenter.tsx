import {useEffect,useState} from 'react';
import {apiFetch} from './api';
import './qms.css';

const menus=[['dashboard','품질 대시보드'],['requirements','요구사항'],['risk-matrix','위험관리'],
 ['traceability','추적성'],['tests','시험·증적'],['defects','결함'],['change-requests','변경관리'],
 ['capas','CAPA'],['documents','문서관리'],['approvals','전자승인'],['audit-packages','감사 패키지'],['audit-chain/status','감사 체인']];
const templates:Record<string,object>={
 requirements:{requirement_id:'REQ-',requirement_type:'SOFTWARE',title:'',description:'',source:'',rationale:'',owner_role:'QA_RA',safety_classification:'UNASSESSED'},
 'risk-matrix':{risk_id:'RISK-',hazard:'',hazardous_situation:'',foreseeable_sequence:'',harm:'',severity:1,probability:1,residual_severity:1,residual_probability:1,risk_controls:[],verification_ids:[],owner_role:'QA_RA'},
 documents:{document_number:'DOC-',document_type:'SOFTWARE_REQUIREMENTS_SPECIFICATION',title:'',requirement_ids:[]},
 'change-requests':{change_id:'CHG-',title:'',description:'',reason:'',affected_tests:[],affected_models:[],affected_risks:[]},
 capas:{error_type:'TEST_FAILURE',severity:'LOW',owner:'',test_ids:[],defect_ids:[],model_ids:[]},
 traceability:{source_type:'REQUIREMENT',source_id:'',relationship:'VERIFIED_BY',target_type:'TEST_SCENARIO',target_id:'',version:1,source_version:1}
};
const actions:Record<string,string[]>={requirements:['submit-review','approve'],documents:['versions','new-version','submit-review','reviews','approve','make-effective','download'],
 'change-requests':['impact-assessment','approve','verify','release'],capas:['root-cause','action-plan','effectiveness-check','close'], 'risk-matrix':['evaluate','approve'], 'audit-packages':['download']};
const actionDefaults:Record<string,object>={approve:{version:1,meaning:'APPROVED',reason:''},'make-effective':{version:1,meaning:'DOCUMENT_EFFECTIVE',reason:''},close:{version:1,meaning:'EFFECTIVENESS_CONFIRMED',reason:''},release:{version:1,meaning:'RELEASE_AUTHORIZED',reason:''},
 'new-version':{expected_version:1,content:'',change_summary:''},reviews:{version:1,decision:'APPROVAL_REQUIRED',comment:''},
 'root-cause':{reason:'',root_cause:''},'action-plan':{reason:'',corrective_action:'',preventive_action:''},'effectiveness-check':{reason:'',effectiveness_check:''},
 'impact-assessment':{assessment_type:'SOFTWARE',impact_level:'HIGH',affected_items:[],regression_scope:['FULL_REGRESSION'],new_risks:[],regulatory_impact:'',cybersecurity_impact:'',privacy_impact:'',interoperability_impact:''}};
const metricLabels:Record<string,string>={requirements:'전체 요구사항',unlinked_requirements:'시험·위험 연결 누락',test_results:'시험 결과',open_defects:'열린 결함',open_capas:'열린 CAPA',pending_documents:'승인 대기 문서',critical_risks:'CRITICAL 위험',traceability_completeness:'추적성 완전성',audit_chain:'감사 체인',release_block:'배포 차단',reason:'차단 사유',clinical_performance:'임상 성능',mode:'구현 상태'};

export default function QmsCenter({baseUrl}:{baseUrl:string}) {
 const [page,setPage]=useState('dashboard'),[data,setData]=useState<unknown>(null),[state,setState]=useState('loading'),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [editor,setEditor]=useState(''),[selected,setSelected]=useState(''),[action,setAction]=useState(''),[actionBody,setActionBody]=useState('{}'),[detail,setDetail]=useState<unknown>(null),[filter,setFilter]=useState('');
 async function request(path:string,method='GET',body?:unknown) {
  const r=await apiFetch(baseUrl+'/api/v1/qms/'+path,{method,headers:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
  if(!r.ok){const d=await r.json();const code=d.detail?.code||'REQUEST_FAILED'; if(r.status===401||r.status===403)setState('permission');else if(code.includes('INTEGRITY'))setState('integrity');throw new Error(code)}
  return r.json();
 }
 async function load(){setState('loading');setError('');try{const value=await request(page);setData(value);setState(Array.isArray(value)&&value.length===0?'empty':'success')}catch(e){setState(s=>s==='permission'||s==='integrity'?s:'error');setError(String(e))}}
 useEffect(()=>{setEditor(JSON.stringify(templates[page]||{},null,2));setSelected('');setDetail(null);setAction('');setFilter('');void load()},[page]);
 async function perform(job:()=>Promise<void>){setBusy(true);setError('');try{await job()}catch(e){setError(e instanceof SyntaxError?'JSON 형식을 확인하세요.':String(e))}finally{setBusy(false)}}
 const collection=Array.isArray(data)?data:page==='risk-matrix'?(data as {risks?:unknown[]})?.risks:[];
 const rows=(collection||[]) as Record<string,unknown>[];
 const path=page==='risk-matrix'?'risks':page;
 async function download(id:string){const r=await apiFetch(`${baseUrl}/api/v1/qms/${path}/${id}/download`);if(!r.ok){setState(r.status===403?'permission':'integrity');throw new Error('다운로드가 차단되었습니다. 권한 또는 무결성을 확인하세요.')}const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=`qms-${id}.${page==='documents'?'md':'zip'}`;a.click();URL.revokeObjectURL(url)}
 return <section className="qms-center" aria-label="QMS 규제 대응 관리센터"><h2>QMS·규제 대응 관리센터</h2>
 <p className="notice">연구·교육용 초안입니다. 규제 적합성·인증·법적 전자서명을 보장하지 않습니다. 실제 환자정보를 입력하지 마세요.</p>
 <nav aria-label="QMS 메뉴">{menus.map(([key,label])=><button key={key} aria-current={page===key?'page':undefined} onClick={()=>setPage(key)}>{label}</button>)}</nav>
 <button disabled={busy} onClick={()=>void load()}>새로고침</button>
 {state==='loading'&&<p role="status">QMS 자료를 불러오는 중입니다.</p>}
 {state==='permission'&&<p role="alert">권한이 없습니다. 서명 세션으로 로그인하고 담당 역할을 확인하세요.</p>}
 {state==='integrity'&&<p role="alert">무결성 검사 실패 — QA/RA 검토가 필요합니다. 다운로드·승인을 진행하지 마세요.</p>}
 {state==='error'&&<p role="alert">불러오지 못했습니다. 연결을 확인한 뒤 새로고침하세요.</p>}
 {error&&<p role="alert">{error} · 입력과 권한을 확인하고 다시 시도하세요.</p>}
 {state==='empty'&&<p role="status">등록된 자료가 없습니다.</p>}
 {state!=='loading'&&state!=='permission'&&<>
 {page==='dashboard'&&data!=null&&<div className="qms-metrics">{Object.entries(data as Record<string,unknown>).map(([key,value])=><article key={key}><h3>{metricLabels[key]||key}</h3><p>{value===null?'NOT_MEASURED':typeof value==='object'?JSON.stringify(value):String(value)}</p></article>)}</div>}
 {rows.length>0&&<><label>목록 필터<input value={filter} onChange={e=>setFilter(e.target.value)}/></label><div className="qms-scroll"><table><caption>{menus.find(x=>x[0]===page)?.[1]} 목록</caption><thead><tr><th>ID</th><th>제목·유형</th><th>상태</th><th>상세</th></tr></thead><tbody>{rows.filter(r=>JSON.stringify(r).includes(filter)).map((row,i)=><tr key={String(row.id||i)}><td>{String(row.requirement_id||row.document_number||row.change_id||row.id||i)}</td><td>{String(row.title||row.name||row.error_type||row.relationship||'—')}</td><td>{String(row.status||row.integrity_status||row.residual_risk||'NOT_VERIFIED')}</td><td><button onClick={()=>{setSelected(String(row.id));setDetail(row)}}>선택 {i+1}</button></td></tr>)}</tbody></table></div></>}
 {page==='traceability'&&<div><button disabled={busy} onClick={()=>perform(async()=>setDetail(await request('traceability/gaps')))}>누락 조회</button><button disabled={busy} onClick={()=>perform(async()=>setDetail(await request('traceability/orphans')))}>고립·버전 불일치 조회</button><p>각 링크의 source/target으로 양방향 관계를 확인합니다.</p></div>}
 {page==='traceability'&&<><button disabled={busy} onClick={()=>perform(async()=>{const r=await apiFetch(baseUrl+'/api/v1/qms/traceability-export');if(!r.ok)throw new Error('CSV 내보내기 권한을 확인하세요.');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download='qms-traceability.csv';a.click();URL.revokeObjectURL(url)})}>추적성 CSV 내보내기</button><TraceGraph rows={rows}/></>}
 {['tests','approvals','audit-chain/status','risk-matrix'].includes(page)&&<pre aria-label="상세 데이터">{JSON.stringify(data,null,2)}</pre>}
 {page==='dashboard'&&<button disabled={busy} onClick={()=>perform(async()=>setDetail(await request('consistency/validate','POST')))}>정합성 검증 실행</button>}
 {page==='audit-packages'&&<button disabled={busy} onClick={()=>perform(async()=>{setDetail(await request('audit-packages','POST'));await load()})}>INCOMPLETE_DRAFT 패키지 생성</button>}
 {templates[page]&&<form onSubmit={e=>{e.preventDefault();void perform(async()=>{setDetail(await request(page==='documents'?'documents/generate':page==='traceability'?'traceability-links':path,'POST',JSON.parse(editor)));await load()})}}><h3>새 자료 작성</h3><p>구조화 JSON 입력입니다. 예시는 측정 결과가 아니며 작성자가 내용을 확인해야 합니다.</p><label>등록 내용<textarea rows={12} value={editor} onChange={e=>setEditor(e.target.value)} spellCheck={false}/></label><button disabled={busy}>서버에 저장</button></form>}
 {selected&&actions[page]&&<form onSubmit={e=>{e.preventDefault();void perform(async()=>{if(action==='download'){await download(selected);return}const method=action==='versions'?'GET':'POST';setDetail(await request(`${path}/${selected}/${action}`,method,method==='GET'?undefined:JSON.parse(actionBody)));await load()})}}><h3>선택 자료 처리: {selected}</h3><label>작업<select required value={action} onChange={e=>{setAction(e.target.value);setActionBody(JSON.stringify(actionDefaults[e.target.value]||{},null,2))}}><option value="">작업 선택</option>{actions[page].map(a=><option key={a}>{a}</option>)}</select></label><label>작업 근거·버전<textarea rows={6} value={actionBody} onChange={e=>setActionBody(e.target.value)}/></label><p>중요 승인은 재인증 미설정으로 차단됩니다. 검토 요청은 승인 완료가 아닙니다.</p><button disabled={busy||!action}>선택 작업 요청</button></form>}
 {detail!=null&&<pre aria-label="작업 결과" role="status">{JSON.stringify(detail,null,2)}</pre>}
 </>}</section>
}

function TraceGraph({rows}:{rows:Record<string,unknown>[]}) {
 if(!rows.length)return null;
 const visible=rows.slice(0,30);
 return <div className="qms-scroll"><p>관계 보기: 최대 30개 링크. 전체 자료는 목록·CSV에서 확인하세요.</p><svg role="img" aria-label="요구사항과 검증 대상의 방향성 관계" viewBox={`0 0 720 ${visible.length*65}`} style={{minWidth:600,width:'100%'}}><defs><marker id="qms-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#183b63"/></marker></defs>{visible.map((row,i)=><g key={String(row.id||i)} transform={`translate(0,${i*65})`}><rect x="0" y="5" width="245" height="48" fill="#edf2f7" stroke="#183b63"/><text x="8" y="24" fontSize="12">{String(row.source_type)}</text><text x="8" y="42" fontSize="10">{String(row.source_id).slice(0,36)}</text><line x1="250" x2="460" y1="34" y2="34" stroke="#183b63" markerEnd="url(#qms-arrow)"/><text x="260" y="20" fontSize="11">{String(row.relationship)}</text><rect x="475" y="5" width="245" height="48" fill="#edf2f7" stroke="#183b63"/><text x="483" y="24" fontSize="12">{String(row.target_type)}</text><text x="483" y="42" fontSize="10">{String(row.target_id).slice(0,36)}</text></g>)}</svg></div>
}
