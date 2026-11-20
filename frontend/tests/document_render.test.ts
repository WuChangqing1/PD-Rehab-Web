import test from 'node:test'
import assert from 'node:assert/strict'
import {renderDocument} from '../src/documents/render.ts'
const d={id:'guide',path:'docs/guide.md',assets:['docs/image.png']}
test('documents render native headings tables fenced code and local assets',()=>{
 const html=renderDocument('# 标题\n\n|项|值|\n|--|--|\n|甲|1|\n\n```ts\nlet x=1\n```\n\n![图](image.png)\n\n[查看](other.md)',d,'/pd-rehab/',[{id:'other',path:'docs/other.md',assets:[]}],{'docs/image.png':'blob:http://localhost/authorized'})
 assert.match(html,/<table>/);assert.match(html,/<pre>/);assert.match(html,/id="标题"/)
 assert.match(html,/blob:http:\/\/localhost\/authorized/)
 assert.match(html,/\/pd-rehab\/docs\/other/)
})
test('raw HTML javascript data remote images and arbitrary relative files cannot execute',()=>{
 const html=renderDocument('<script>alert(1)</script>\n\n[x](javascript:alert(1))\n\n![x](https://evil.invalid/a)\n\n[x](../../.env)\n\n[x](data:text/html,x)',d)
 assert.doesNotMatch(html,/<script|src="https:|href="javascript:|href="data:|href="[^"\n]*\.env/)
 assert.match(html,/&lt;script&gt;/)
})
test('malformed encoded links disable only that link instead of aborting the document',()=>{
 for(const value of ['%FF','%C0%AF','%E0%A4%A','image%80.png']){
  const html=renderDocument(`# 仍可阅读\n\n[链接](${value})\n\n后续正文`,d)
  assert.match(html,/后续正文/);assert.doesNotMatch(html,/href="%/)
 }
})

test('documents have linked contents and unique duplicate heading anchors',()=>{
 const html=renderDocument('# 标题\n\n## 小节\n\n## 小节',d)
 assert.match(html,/aria-label="文档目录"/)
 assert.match(html,/href="#小节-1"/)
 assert.match(html,/id="小节-1"/)
})

import {sourceLink} from '../src/documents/sourceLinks.ts'
test('AI citations open the matching local document route on root and subpath deployments',()=>{
 assert.equal(sourceLink('https://ccqspace.site/pd-rehab/docs/piano#双手','/'),'/docs/piano#%E5%8F%8C%E6%89%8B')
 assert.equal(sourceLink('https://ccqspace.site/pd-rehab/docs/piano','/pd-rehab/'),'/pd-rehab/docs/piano')
 assert.equal(sourceLink('javascript:alert(1)'),undefined)
 assert.equal(sourceLink('https://github.com/secret'),undefined)
})
