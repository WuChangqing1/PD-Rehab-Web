export interface StaffRegistration {username:string;password:string;display_name:string;phone:string;requested_role:'DOCTOR'|'NURSE'}
export interface ApplicationReceipt {id:string;status:'PENDING'}
export function createStaffRegistrationApi(base:string,request:typeof fetch=fetch) {
 return async(payload:StaffRegistration):Promise<ApplicationReceipt>=>{
  let response:Response
  try{response=await request(`${base.replace(/\/$/,'')}/api/auth/register`,{method:'POST',credentials:'omit',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(20000)})}catch{throw Error('无法连接到服务器，请检查网络后重试。')}
  const data=await response.json().catch(()=>({}))
  if(!response.ok)throw Error(data?.error?.message||'申请提交失败，请稍后重试。')
  if(!data.id||data.status!=='PENDING')throw Error('申请提交失败，请稍后重试。')
  return {id:data.id,status:'PENDING'}
 }
}
export class StaffRegistrationController {
 form:StaffRegistration={username:'',password:'',display_name:'',phone:'',requested_role:'DOCTOR'}
 submitting=false;error='';result:ApplicationReceipt|null=null;private alive=true
 private register:(payload:StaffRegistration)=>Promise<ApplicationReceipt>
 constructor(register:(payload:StaffRegistration)=>Promise<ApplicationReceipt>){this.register=register}
 async submit(){
  if(this.submitting||this.result||!this.alive)return
  if(!['DOCTOR','NURSE'].includes(this.form.requested_role)||!this.form.username.trim()||!this.form.password||!this.form.display_name.trim()||!this.form.phone.trim()){this.error='请完整填写申请资料。';return}
  if(this.form.display_name.trim().length>128||/\p{C}/u.test(this.form.display_name.trim())){this.error='请填写有效姓名';return}
  if(!/^[A-Za-z0-9_]{3,32}$/.test(this.form.username.trim())){this.error='用户名须为3至32位字母、数字或下划线。';return}
  if(this.form.password.length<8||this.form.password.length>64){this.error='密码须为8至64位。';return}
  if(new TextEncoder().encode(this.form.password).length>72){this.error='密码的UTF-8编码不能超过72字节，请减少字符。';return}
  if(!/^\+?[0-9 -]{6,32}$/.test(this.form.phone.trim())){this.error='请填写有效联系电话。';return}
  this.submitting=true;this.error=''
  try{const data=await this.register({...this.form,username:this.form.username.trim(),display_name:this.form.display_name.trim(),phone:this.form.phone.trim()});if(this.alive){this.result={id:data.id,status:'PENDING'};this.form.password=''}}
  catch(error){if(this.alive)this.error=error instanceof Error?error.message:'申请提交失败，请稍后重试。'}
  finally{if(this.alive)this.submitting=false}
 }
 dispose(){this.alive=false;this.form.password=''}
}
export interface StaffApplication {id:string;username:string;display_name:string;phone:string;requested_role:'DOCTOR'|'NURSE';status:'PENDING'|'APPROVED'|'REJECTED';reason:string|null;created_at:string}
export interface ManagedStaff {id:string;username:string;display_name:string;role:'ADMIN'|'DOCTOR'|'NURSE';is_active:boolean}
export interface StaffManagementApi {
 applications:(status:string)=>Promise<{items:StaffApplication[];total:number}>
 staff:()=>Promise<{items:ManagedStaff[];total:number}>
 review:(id:string,payload:{decision:'APPROVE'|'REJECT';role?:'DOCTOR'|'NURSE';reason?:string})=>Promise<unknown>
 update:(id:string,payload:{role?:'DOCTOR'|'NURSE';is_active?:boolean})=>Promise<unknown>
}
export class StaffManagementController {
 status='PENDING';applications:StaffApplication[]=[];staff:ManagedStaff[]=[];loading=false;busy=false;error='';private revision=0;private alive=true
 private api:StaffManagementApi
 constructor(api:StaffManagementApi){this.api=api}
 async load(){const rev=++this.revision;this.loading=true;this.error='';try{const [applications,staff]=await Promise.all([this.api.applications(this.status),this.api.staff()]);if(this.alive&&rev===this.revision){this.applications=applications.items;this.staff=staff.items}}catch(error){if(this.alive&&rev===this.revision)this.error=error instanceof Error?error.message:'无法加载医护账户。'}finally{if(this.alive&&rev===this.revision)this.loading=false}}
 async review(id:string,decision:'APPROVE'|'REJECT',role:'DOCTOR'|'NURSE',reason:string){if(this.busy)return;this.busy=true;this.error='';try{await this.api.review(id,{decision,...(decision==='APPROVE'?{role}:{}),...(reason.trim()?{reason:reason.trim()}:{})});if(this.alive)await this.load()}catch(error){if(this.alive)this.error=error instanceof Error?error.message:'账户操作失败，请重试。'}finally{if(this.alive)this.busy=false}}
 async update(id:string,payload:{role?:'DOCTOR'|'NURSE';is_active?:boolean}):Promise<boolean>{if(this.busy||!this.alive)return false;this.busy=true;this.error='';try{await this.api.update(id,payload);if(this.alive)await this.load();return this.alive}catch(error){if(this.alive)this.error=error instanceof Error?error.message:'账户操作失败，请重试。';return false}finally{if(this.alive)this.busy=false}}
 dispose(){this.alive=false;this.revision++}
}
