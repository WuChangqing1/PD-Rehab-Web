export interface TrainingReference { kind:'piano'|'pose'|'song'; id:string }
export class ReviewOffers {
 private seen=new Set<string>()
 private pending:TrainingReference|null=null
 offer(row:TrainingReference,saved:boolean,interrupted:boolean):boolean {
  const key=`${row.kind}:${row.id}`
  if(!saved||interrupted||!row.id||this.seen.has(key))return false
  this.seen.add(key);this.pending={...row};return true
 }
 take():TrainingReference|null {const row=this.pending;this.pending=null;return row}
 clear(){this.seen.clear();this.pending=null}
}
