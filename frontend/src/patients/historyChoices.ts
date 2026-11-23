/** Only explicit selections change the stored text; arbitrary legacy text survives. */
export function toggleChoice(original:unknown,choice:string,selected:boolean):string {
 const values=String(original??'').split('；').map(x=>x.trim()).filter(Boolean)
 const next=values.filter(x=>x!==choice)
 if(selected)next.push(choice)
 return next.join('；')
}
export function hasChoice(original:unknown,choice:string):boolean {return String(original??'').split('；').map(x=>x.trim()).includes(choice)}
