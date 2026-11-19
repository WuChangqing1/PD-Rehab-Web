import { http } from '@/api/client'
import type { StaffApplication,ManagedStaff,StaffManagementApi } from './controller'
export const staffManagementApi:StaffManagementApi={
 async applications(status){return (await http.get<{items:StaffApplication[];total:number}>('/auth/staff-applications',{params:{status}})).data},
 async staff(){return (await http.get<{items:ManagedStaff[];total:number}>('/auth/staff')).data},
 async review(id,payload){return (await http.post(`/auth/staff-applications/${encodeURIComponent(id)}/review`,payload)).data},
 async update(id,payload){return (await http.patch(`/auth/staff/${encodeURIComponent(id)}`,payload)).data},
}
