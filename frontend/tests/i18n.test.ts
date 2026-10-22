import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import * as core from '../src/i18n/core.ts'
const require=createRequire(import.meta.url)
import {createTranslator, normalizeLocale, readLocale, persistLocale} from '../src/i18n/core.ts'
const messages={'工作台':'Dashboard','帕琴律动':'Paqin Rhythm','第 {0} / {1} 轮':'Round {0} / {1}','删除 {0} 的评估？':'Delete the assessment for {0}?'}
test('Chinese is the default; unsupported saved values do not choose an arbitrary language',()=>{
 assert.equal(normalizeLocale(null),'zh-CN');assert.equal(normalizeLocale('en'),'en');assert.equal(normalizeLocale('fr'),'zh-CN')
})
test('language persistence handles blocked storage and malformed values',()=>{
 assert.equal(readLocale({getItem:()=>{throw Error('blocked')}}),'zh-CN')
 assert.equal(readLocale({getItem:()=> 'en'}),'en')
 let saved='';persistLocale({setItem:(_k,v)=>{saved=v}},'en');assert.equal(saved,'en')
 assert.doesNotThrow(()=>persistLocale({setItem:()=>{throw Error('blocked')}},'en'))
})
test('exact UI labels translate and Chinese round trips without changing source data',()=>{
 const t=createTranslator(messages)
 assert.equal(t('工作台','en'),'Dashboard');assert.equal(t('工作台','zh-CN'),'工作台')
 assert.equal(t('小明','en'),'小明');assert.equal(t('未知的患者备注','en'),'未知的患者备注')
 assert.equal(t(0,'en'),'0');assert.equal(t(null,'en'),'')
})
test('parameterized messages preserve numbers, patient identities and punctuation',()=>{
 const t=createTranslator(messages)
 assert.equal(t('第 2 / 3 轮','en'),'Round 2 / 3')
 assert.equal(t('删除 张三 [A].* 的评估？','en'),'Delete the assessment for 张三 [A].*?')
})
test('unknown messages remain visible instead of disappearing or translating arbitrary substrings',()=>{
 const t=createTranslator(messages)
 assert.equal(t('我的工作台备注','en'),'我的工作台备注')
 assert.equal(t('the recorded value','en'),'the recorded value')
})

test('message punctuation is literal and cannot match a different UI message',()=>{
 const t=createTranslator({'质量[手部] ({0}) + {1}?':'Quality [hand] ({0}) + {1}?'})
 assert.equal(t('质量[手部] (A) + 2?','en'),'Quality [hand] (A) + 2?')
 assert.equal(t('质量手 (A) 2','en'),'质量手 (A) 2')
})
test('all shipping catalogs compile and every parameterized message preserves its slots',()=>{
 const files=['general','piano','patients','extra','errors','dynamic','models']
 const all=Object.assign({},...files.map(name=>JSON.parse(readFileSync(new URL(`../src/i18n/en-${name}.json`,import.meta.url),'utf8'))))
 const t=createTranslator(all)
 for(const [key,value] of Object.entries(all)){
   const sample=key.replace(/\{(\d+)\}/g,(_slot,n)=>`value-${n}`)
   const expected=(value as string).replace(/\{(\d+)\}/g,(_slot,n)=>`value-${n}`)
   assert.equal(t(sample,'en'),expected,`translation for ${key}`)
 }
})

test('live language changes update reactive UI and remember selection without changing record data',async()=>{
 const vue=require('vue'),ts=require('typescript')
 const source=readFileSync(new URL('../src/i18n/index.ts',import.meta.url),'utf8')
 const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText
 const values=new Map<string,string>(),storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value)}
 const document={documentElement:{lang:'zh-CN'}},output:any={}
 new Function('require','exports','document','localStorage',compiled)((name:string)=>name==='vue'?vue:name==='./core'?core:JSON.parse(readFileSync(new URL('../src/i18n/'+name.replace('./',''),import.meta.url),'utf8')),output,document,storage)
 const draft=vue.reactive({name:'小明',notes:'工作台',sessionId:'saved-123',hits:7})
 const before=JSON.stringify(draft),views:string[]=[]
 const scope=vue.effectScope();scope.run(()=>vue.watchEffect(()=>views.push(output.t('工作台'))))
 output.setLocale('en');await vue.nextTick()
 assert.equal(output.t('工作台'),'Dashboard');assert.equal(output.pageTitle('患者档案'),'Patient records · Paqin Rhythm')
 assert.equal(document.documentElement.lang,'en');assert.equal(values.get(core.LANGUAGE_STORAGE_KEY),'en')
 assert.equal(JSON.stringify(draft),before)
 output.setLocale('zh-CN');await vue.nextTick()
 assert.equal(output.t('工作台'),'工作台');assert.equal(document.documentElement.lang,'zh-CN')
 assert.deepEqual(views,['工作台','Dashboard','工作台']);assert.equal(JSON.stringify(draft),before);scope.stop()
})

test('optional patient values are raw by default even when identical to a translated UI label',async()=>{
 const vue=require('vue'),{renderToString}=require('@vue/server-renderer')
 const source=readFileSync(new URL('../src/components/OptionalValue.vue',import.meta.url),'utf8')
 const template=source.match(/<template>([\s\S]*?)<\/template>/)![1]
 const {code}=require('@vue/compiler-dom').compile(template,{mode:'function',prefixIdentifiers:true})
 const component={props:['value','localize'],setup:()=>({displayOptionalValue:(v:unknown)=>v==null?'—':String(v)}),render:new Function('Vue',code)(vue)}
 for(const value of ['工作台','正常','一','保持']){
   const app=vue.createSSRApp(component,{value});app.config.globalProperties.$t=createTranslator({'工作台':'Dashboard','正常':'Active','一':'Mon','保持':'Hold'})
   // The Vue adapter normally supplies locale; this intentionally simulates English.
   const translate=createTranslator({'工作台':'Dashboard','正常':'Active','一':'Mon','保持':'Hold'})
   app.config.globalProperties.$t=(input:unknown)=>translate(input,'en')
   assert.ok((await renderToString(app)).includes('>'+value+'</span>'))
 }
 const app=vue.createSSRApp(component,{value:'工作台',localize:true});app.config.globalProperties.$t=(input:unknown)=>createTranslator({'工作台':'Dashboard'})(input,'en')
 assert.ok((await renderToString(app)).includes('>Dashboard</span>'))
})

test('chart localization preserves source samples, IDs and callback numeric values',()=>{
 const ts=require('typescript'),source=readFileSync(new URL('../src/i18n/charts.ts',import.meta.url),'utf8')
 const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 const translate=createTranslator({'准确率':'Accuracy','工作台':'Dashboard'}),output:any={}
 new Function('require','exports',compiled)(()=>({t:(value:unknown)=>translate(value,'en')}),output)
 const samples=[{name:'工作台',value:0},['工作台',0.8]]
 const original={id:'工作台',yAxis:{name:'准确率'},series:[{name:'准确率',data:samples}],tooltip:{valueFormatter:()=>0}}
 const translated=output.localizeChartOption(original)
 assert.equal(translated.yAxis.name,'Accuracy');assert.equal(translated.series[0].name,'Accuracy')
 assert.equal(translated.series[0].data,samples);assert.equal(translated.id,'工作台')
 assert.equal(translated.tooltip.valueFormatter(),0);assert.equal(original.yAxis.name,'准确率')
})
