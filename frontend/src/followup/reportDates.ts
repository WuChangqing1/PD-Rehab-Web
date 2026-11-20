export type ReportDates = [] | [string,string]
export function reportPreset(preset:'7'|'30'|'month'|'all', now=new Date()):ReportDates {
 if(preset==='all')return []
 const end=new Date(now.getTime()+8*3600_000).toISOString().slice(0,10)
 const start=new Date(end+'T00:00:00Z')
 if(preset==='month')start.setUTCDate(1)
 else start.setUTCDate(start.getUTCDate()-Number(preset)+1)
 return [start.toISOString().slice(0,10),end]
}
export function reportParams(patientId:string|null,dates:ReportDates){
 if(!patientId)throw new Error('请先选择患者。')
 if(!dates.length)return {}
 if(dates.some(d=>!/^\d{4}-\d{2}-\d{2}$/.test(d)||!Number.isFinite(Date.parse(d))||new Date(d).toISOString().slice(0,10)!==d)||dates[0]>dates[1])throw new Error('请选择有效的开始和结束日期。')
 return {start_date:dates[0],end_date:dates[1]}
}
