// Public release checks only; independent demo feed is checked separately on server.
import {readFile,writeFile} from 'node:fs/promises'
import {createHash} from 'node:crypto'
import assert from 'node:assert/strict'
const checks=[]
for(const [base,folder] of [['https://ccqspace.site/pd-rehab/','frontend/dist-under-path/'],['http://110.42.236.65:18085/','frontend/dist/']]){
 const response=await fetch(base);assert.equal(response.status,200)
 const body=Buffer.from(await response.arrayBuffer());assert.deepEqual(body,await readFile(folder+'index.html'))
 const health=await(await fetch(new URL('api/system/health',base))).json();assert.equal(health.status,'ok')
 const models=await(await fetch(new URL('api/system/models',base))).json()
 assert.equal(models.models.micro_expression_model.extra.adapter,'microflow_da')
 assert.equal(models.models.micro_expression_model.is_ready,false)
 for(const asset of [body.toString().match(/<script[^>]*src="([^"]+)"/)[1],'images/ballet-studio-cover-20261017.png']){
  const remote=await fetch(new URL(asset,base));assert.equal(remote.status,200)
  const relative=asset.includes('/assets/')?asset.split('/').slice(-2).join('/'):asset
  assert.equal(createHash('sha256').update(Buffer.from(await remote.arrayBuffer())).digest('hex'),createHash('sha256').update(await readFile(folder+relative)).digest('hex'))
 }
 const deep=await fetch(new URL('follow-up?patientId=abfd9bed-4644-5fd2-812f-3a7eaca11a84',base))
 assert.equal(deep.status,200);assert.deepEqual(Buffer.from(await deep.arrayBuffer()),body)
 const anonymous=await fetch(new URL('api/patients/abfd9bed-4644-5fd2-812f-3a7eaca11a84/follow-up?start_date=2026-10-01&end_date=2026-10-31',base))
 assert.equal(anonymous.status,401)
 checks.push({base,indexMatches:true,entryAssetMatches:true,dancingCoverMatches:true,deepLink:true,health:'ok',unauthenticatedFeed:401,modelConfigPreserved:true})
}
const result={verifiedAt:new Date().toISOString(),checks,realPatientDataAccessed:false}
await writeFile('docs/followup-calendar-20261017/production-verification.json',JSON.stringify(result,null,2)+'\n')
console.log(JSON.stringify(result))
