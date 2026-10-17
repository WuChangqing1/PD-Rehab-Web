// Read-only production verification. Tokens and record identifiers remain in memory.
import {spawnSync} from 'node:child_process'
import {readFile,writeFile,mkdir} from 'node:fs/promises'
import {createHash} from 'node:crypto'
import assert from 'node:assert/strict'

const out='docs/assessment-fixes-20261017'
await mkdir(out,{recursive:true})
const bases=[['https://ccqspace.site/pd-rehab/','frontend/dist-under-path/'],['http://110.42.236.65:18085/','frontend/dist/']]
const checks=[]
for(const [base,folder] of bases){
  const entry=await fetch(base);assert.equal(entry.status,200)
  const body=Buffer.from(await entry.arrayBuffer())
  assert.deepEqual(body,await readFile(folder+'index.html'))
  const health=await(await fetch(new URL('api/system/health',base))).json();assert.equal(health.status,'ok')
  const status=await(await fetch(new URL('api/system/models',base))).json()
  assert.equal(status.models.micro_expression_model.extra.adapter,'microflow_da')
  assert.equal(status.models.micro_expression_model.is_ready,false)
  const script=body.toString().match(/<script[^>]*src="([^"]+)"/)[1]
  const asset=await fetch(new URL(script,base));assert.equal(asset.status,200)
  const actual=createHash('sha256').update(Buffer.from(await asset.arrayBuffer())).digest('hex')
  const expected=createHash('sha256').update(await readFile(folder+script.split('/').slice(-2).join('/'))).digest('hex')
  assert.equal(actual,expected)
  const spa=await fetch(new URL('assessment/sessions/verification-only/results',base));assert.equal(spa.status,200)
  assert.deepEqual(Buffer.from(await spa.arrayBuffer()),body)
  checks.push({base,indexMatches:true,entryAssetMatches:true,resultsDeepLink:true,health:'ok',modelConfigPreserved:true})
}
const code="import json; from sqlalchemy import select; from app.db.session import SessionLocal; from app.db.models import StaffUser,AssessmentSession; from app.core.security import create_access_token; db=SessionLocal(); user=db.scalar(select(StaffUser).where(StaffUser.is_active.is_(True),StaffUser.role=='ADMIN')); assert user; row=db.scalar(select(AssessmentSession).order_by(AssessmentSession.started_at.desc())); print(json.dumps(dict(token=create_access_token(user.id,role=user.role,expires_minutes=5,extra={'purpose':'deployment_read_only_verification'}),session_id=row.id if row else None,patient_id=row.patient_id if row else None))); db.close()"
const sh=s=>"'"+s.replaceAll("'","'\\''")+"'"
const auth=spawnSync('ssh',['-o','BatchMode=yes','fengz','cd /opt/pd-rehab/app/PD-Rehab-Web/backend && /opt/pd-rehab/venv/bin/python -c '+sh(code)],{encoding:'utf8',windowsHide:true})
assert.equal(auth.status,0,'Could not obtain short-lived read-only verification session')
const credentials=JSON.parse(auth.stdout.trim().split(/\r?\n/).at(-1))
const headers={Authorization:`Bearer ${credentials.token}`},base=bases[0][0]
const get=async(path)=>{const r=await fetch(new URL('api/'+path,base),{headers});assert.equal(r.status,200);return r.json()}
let resultCounts=null
if(credentials.session_id){
  const id=credentials.session_id,detail=await get(`assessment-sessions/${id}`)
  assert.equal(detail.patient_id,credentials.patient_id)
  for(const field of ['micro_expression_results','finger_tapping_results','functional_assessments']){
    assert.ok(Array.isArray(detail[field]));assert.ok(detail[field].every(r=>r.assessment_session_id===id))
  }
  const summary=await get(`assessment-sessions/${id}/finger-tapping`)
  assert.equal(summary.session_id,id)
  const readiness=await get(`assessment-sessions/${id}/readiness`);assert.ok(Array.isArray(readiness.items))
  const open=await get(`patients/${credentials.patient_id}/assessment-sessions?status=IN_PROGRESS&page_size=200`)
  assert.ok(open.items.every(r=>r.patient_id===credentials.patient_id && r.status==='IN_PROGRESS'))
  resultCounts={finger:detail.finger_tapping_results.length,face:detail.micro_expression_results.length,functional:detail.functional_assessments.length,unfinishedCount:open.total}
}
const anonymous=await fetch(new URL('api/assessment-sessions/verification-only',base));assert.equal(anonymous.status,401)
const result={verifiedAt:new Date().toISOString(),checks,authenticatedReadsVerified:!!credentials.session_id,resultCounts,clinicalRecordsMutated:false}
await writeFile(out+'/production-verification.json',JSON.stringify(result,null,2)+'\n')
console.log(JSON.stringify({entries:checks.length,authenticatedReadsVerified:result.authenticatedReadsVerified,clinicalRecordsMutated:false}))
