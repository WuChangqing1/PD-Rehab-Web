// Public production verification only: no authentication or clinical data access.
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
const base=bases[0][0]
const anonymous=await fetch(new URL('api/assessment-sessions/verification-only',base));assert.equal(anonymous.status,401)
const result={verifiedAt:new Date().toISOString(),checks,authenticatedReadsVerified:false,clinicalDataAccessed:false,clinicalRecordsMutated:false}
await writeFile(out+'/production-verification.json',JSON.stringify(result,null,2)+'\n')
console.log(JSON.stringify({entries:checks.length,clinicalDataAccessed:false,clinicalRecordsMutated:false}))
