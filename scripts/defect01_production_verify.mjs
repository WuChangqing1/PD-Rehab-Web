// Public static/health checks only. Never authenticate or access patient data.
import {readFile,writeFile} from 'node:fs/promises'
import {createHash} from 'node:crypto'
import assert from 'node:assert/strict'
const manifest=JSON.parse(await readFile('_deploy/defect01-release-20261018/assets.json','utf8'))
const digest=bytes=>createHash('sha256').update(bytes).digest('hex')
const checks=[]
for(const [base,variant] of [['https://ccqspace.site/pd-rehab/','dist-under-path'],['http://110.42.236.65:18085/','dist']]){
 const response=await fetch(base);assert.equal(response.status,200)
 const body=Buffer.from(await response.arrayBuffer());assert.equal(digest(body),manifest[variant+'/index.html'])
 const health=await(await fetch(new URL('api/system/health',base))).json();assert.equal(health.status,'ok')
 const paths=Object.keys(manifest).filter(name=>name.startsWith(variant+'/assets/')&&/\/Patient(?:Form|Detail|s)Page-[\w-]+\.js$/.test(name))
 assert.equal(paths.length,3)
 for(const name of paths){
  const remote=await fetch(new URL(name.slice(variant.length+1),base));assert.equal(remote.status,200)
  assert.equal(digest(Buffer.from(await remote.arrayBuffer())),manifest[name])
 }
 const deep=await fetch(new URL('patients/new',base));assert.equal(deep.status,200)
 assert.equal(digest(Buffer.from(await deep.arrayBuffer())),digest(body))
 const anonymous=await fetch(new URL('api/patients',base));assert.equal(anonymous.status,401)
 checks.push({base,indexMatches:true,patientChunksVerified:paths.length,deepLink:true,health:'ok',unauthenticatedPatients:401})
}
const result={verifiedAt:new Date().toISOString(),checks,realPatientDataAccessed:false}
await writeFile('docs/defect01-20261018/production-verification.json',JSON.stringify(result,null,2)+'\n')
console.log(JSON.stringify(result))
