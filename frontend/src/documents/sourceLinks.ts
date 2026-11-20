/** Canonical API citations stay absolute for App, same-site for the Web viewer. */
export function sourceLink(value:string,base='/pd-rehab/'):string|undefined {
 try {
  const url=new URL(value)
  const match=url.pathname.match(/^\/pd-rehab\/docs\/([a-z][a-z0-9-]{0,79})$/)
  if(url.origin!=='https://ccqspace.site'||url.username||url.password||!match)return undefined
  return `${base.replace(/\/?$/,'/')}docs/${match[1]}${url.hash}`
 }catch{return undefined}
}
