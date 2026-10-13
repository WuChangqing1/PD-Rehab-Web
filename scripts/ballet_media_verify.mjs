import { chromium } from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
const url=process.argv[2] || 'http://127.0.0.1:18773/ballet-review/';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
await mkdir('artifacts/ballet-review',{recursive:true});
const results=[];
for(const [name,width,height] of [['pc',1440,1000],['tablet',820,1180],['mobile',390,844]]) {
 const page=await browser.newPage({viewport:{width,height}}); const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url);await page.locator('h1').waitFor();
 for(let i=0;i<2;i++) {const v=page.locator('video').nth(i);await v.evaluate(v=>v.play());await page.waitForFunction(i=>document.querySelectorAll('video')[i].currentTime>.3,i);await v.evaluate(v=>v.pause());}
 await page.locator('video').first().evaluate(v=>v.play());await page.locator('video').nth(1).evaluate(v=>v.play());
 if(!await page.locator('video').first().evaluate(v=>v.paused))throw new Error('Concurrent audio/video playback');
 await page.locator('video').nth(1).evaluate(v=>v.pause());
 const state=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,images:[...document.images].every(i=>i.complete&&i.naturalWidth>0),videos:[...document.querySelectorAll('video')].map(v=>({duration:v.duration,width:v.videoWidth,muted:v.muted}))}));
 if(state.overflow||!state.images||errors.length)throw new Error(JSON.stringify({state,errors}));
 await page.screenshot({path:`artifacts/ballet-review/${url.startsWith('https')?'live':'local'}-${name}.png`,fullPage:true});results.push({name,...state,errors});await page.close();
}
await browser.close();await writeFile('artifacts/ballet-review/browser-results.json',JSON.stringify({url,results},null,2));console.log(JSON.stringify(results));
