export function permissionsFor(role: unknown) {
 return {staff:['ADMIN','DOCTOR','NURSE'].includes(String(role)),admin:role==='ADMIN',clinical:role==='ADMIN'||role==='DOCTOR'}
}
export function canDeleteAssessment(role:unknown,userId:string,session:{status:string;created_by:string|null}) {
 return role==='ADMIN'||(permissionsFor(role).staff&&['PENDING','IN_PROGRESS','ABORTED'].includes(session.status)&&session.created_by===userId)
}
export function patientPayloadFor(role:unknown,payload:Record<string,unknown>):Record<string,unknown> {
 return permissionsFor(role).staff ? {...payload} : {}
}
export function canManageRecording(role:unknown,userId:string,row:{status:string;operator_id?:string},action:'delete'|'retry') {
 if(role==='ADMIN')return true
 if(!permissionsFor(role).staff||row.operator_id!==userId)return false
 return action==='retry'||!['SUCCESS','PARTIAL_SUCCESS','NO_VALID_SEGMENTS'].includes(row.status)
}
