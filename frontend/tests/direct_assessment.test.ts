import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
for(const page of ['MicroExpressionPage.vue','FingerTappingPage.vue']){
 test(page+' exposes one capture flow without a separate start-check mode',()=>{
  const source=readFileSync(new URL('../src/pages/'+page,import.meta.url),'utf8')
  const template=source.split('<template>')[1]??''
  assert.equal(/PatientTaskLayout|function startTask|const started/.test(source),false,'the redundant check mode must be removed')
  assert.equal([...template.matchAll(/<VideoCapturePanel\b/g)].length,1)
  assert.equal(/开始检查|进入检查界面|使用简洁检查界面/.test(template),false)
  assert.match(template,/录制|VideoCapturePanel/)
  assert.match(template,/FaceAnalysisResult|MetricSummaryCards/)
 })
}

test('shared capture guidance does not instruct finger patients to make facial expressions',()=>{
 const panel=readFileSync(new URL('../src/components/VideoCapturePanel.vue',import.meta.url),'utf8')
 assert.equal(panel.includes('先保持自然表情'),false)
 assert.equal(panel.includes('录制已完成，请确认下方片段后开始分析。'),false)
})
