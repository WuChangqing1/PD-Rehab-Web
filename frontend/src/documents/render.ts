import MarkdownIt from 'markdown-it'
export interface HostedDocument {id:string;path:string;assets:string[]}
export function renderDocument(markdown:string,doc:HostedDocument,base='/pd-rehab/',entries:HostedDocument[]=[],assetUrls:Record<string,string>={}):string {
  const md=new MarkdownIt({html:false,linkify:false,typographer:false})
  function local(raw:string,image=false):string|null {
    if(raw.startsWith('#'))return image?null:raw
    if(/^(?:https:|mailto:)/i.test(raw))return image?null:raw
    if(/^(?:[a-z]+:|\/\/|\/|\\)/i.test(raw))return null
    let url:URL,path:string
    try {url=new URL(raw,'https://docs.invalid/'+doc.path);path=decodeURIComponent(url.pathname.slice(1))}
    catch {return null}
    if(image)return doc.assets.includes(path)?(assetUrls[path]??null):null
    const target=entries.find(x=>x.path===path)
    return target?`${base}docs/${target.id}${url.hash}`:null
  }
  md.renderer.rules.link_open=(ts,i,opts,_env,self)=>{
    const token=ts[i]!,href=local(token.attrGet('href')??'')
    if(href)token.attrSet('href',href)
    else {token.attrs=(token.attrs??[]).filter(x=>x[0]!=='href');token.attrSet('aria-disabled','true');token.attrSet('title','链接未发布')}
    token.attrSet('rel','noopener noreferrer')
    return self.renderToken(ts,i,opts)
  }
  md.renderer.rules.image=(ts,i)=>{
    const token=ts[i]!,src=local(token.attrGet('src')??'',true)
    return src?`<img src="${md.utils.escapeHtml(src)}" alt="${md.utils.escapeHtml(token.content)}" loading="lazy">`:`<span>${md.utils.escapeHtml(token.content)}（附件未发布）</span>`
  }
  const headings:Array<{id:string;text:string}>=[],used=new Map<string,number>()
  md.renderer.rules.heading_open=(ts,i,opts,_env,self)=>{
    const text=ts[i+1]?.content??''
    const slug=text.toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu,'').replace(/\s+/g,'-')||'section'
    const count=used.get(slug)??0;used.set(slug,count+1)
    const id=count?`${slug}-${count}`:slug
    ts[i]!.attrSet('id',id);headings.push({id,text})
    return self.renderToken(ts,i,opts)
  }
  const body=md.render(markdown)
  const toc=headings.length>1?'<nav aria-label="文档目录"><strong>目录</strong><ol>'+headings.map(x=>`<li><a href="#${md.utils.escapeHtml(x.id)}">${md.utils.escapeHtml(x.text)}</a></li>`).join('')+'</ol></nav>':''
  return toc+body
}
