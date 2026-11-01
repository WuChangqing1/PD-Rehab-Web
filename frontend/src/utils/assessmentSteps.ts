interface Step{key:string;label:string;state:string}
export function comprehensiveSteps(items:Step[]):Step[]{
 const hands=items.filter(item=>item.key==='finger_tapping_left'||item.key==='finger_tapping_right')
 let added=false
 return items.flatMap(item=>{
  if(!hands.includes(item))return [item]
  if(added)return []
  added=true
  return [{key:'finger_tapping',label:'手指敲击',state:
   hands.length===2&&hands.every(hand=>hand.state==='COMPLETED')?'COMPLETED':'PENDING'}]
 })
}
