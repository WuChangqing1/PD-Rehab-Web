"""Public staff applications and administrator-only account lifecycle."""
from typing import Literal
import unicodedata
from fastapi import APIRouter, Request, Query, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, func
from app.api.deps import DbSession, AdminUser
from app.api.mobile_auth import Login, begin_auth_write, rate_limit, no_store
from app.core.errors import conflict, not_found
from app.core.security import hash_password
from app.db.base import utcnow
from app.db.models import StaffUser
from app.db.models.staff_application import StaffApplication
from app.schemas.auth import StaffUserRead

router = APIRouter(prefix='/auth', tags=['Staff accounts'], dependencies=[Depends(no_store)])

class ApplicationIn(Login):
    display_name: str = Field(min_length=1,max_length=128)
    phone: str = Field(pattern=r'^\+?[0-9 -]{6,32}$')
    requested_role: Literal['DOCTOR','NURSE']

    @field_validator('display_name')
    @classmethod
    def name(cls,value):
        if any(unicodedata.category(c).startswith('C') for c in value):raise ValueError('姓名不能包含控制字符')
        value=value.strip()
        if not value: raise ValueError('请填写有效姓名')
        return value

class Review(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['APPROVE','REJECT']
    role: Literal['DOCTOR','NURSE'] | None = None
    reason: str | None = Field(None,max_length=1000)

class StaffPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['ADMIN','DOCTOR','NURSE'] | None = None
    is_active: bool | None = None

def public(row):
    return {key:getattr(row,key) for key in ('id','username','display_name','phone','requested_role','status','reason','reviewed_by','reviewed_at','created_at','user_id')}

def username_taken(db, username):
    return (db.scalar(select(StaffUser.id).where(func.lower(StaffUser.username)==username.lower())) is not None
        or db.scalar(select(StaffApplication.id).where(func.lower(StaffApplication.username)==username.lower(),StaffApplication.status=='PENDING')) is not None)

def serialize_management(db,user):
    begin_auth_write(db)
    # One stable lock for the last-admin invariant, even when different admins
    # are modified concurrently. SQLite BEGIN IMMEDIATE serializes processes.
    if db.get_bind().dialect.name != 'sqlite':
        db.scalars(select(StaffUser).where(StaffUser.role=='ADMIN').order_by(StaffUser.id).with_for_update()).all()
    db.refresh(user)
    if user.role!='ADMIN' or not user.is_active:
        from app.core.errors import forbidden
        raise forbidden('管理员权限已变化，请刷新。')

@router.post('/register',status_code=201)
def register(payload:ApplicationIn,db:DbSession,request:Request):
    rate_limit(request,'staff-register',6)
    begin_auth_write(db)
    if username_taken(db,payload.username): raise conflict('该用户名不可用。')
    row=StaffApplication(username=payload.username,password_hash=hash_password(payload.password),display_name=payload.display_name,phone=payload.phone,requested_role=payload.requested_role)
    db.add(row);db.commit();db.refresh(row)
    return {'id':row.id,'status':row.status,'message':'申请已提交，请等待管理员审核。'}

@router.get('/staff-applications')
def applications(db:DbSession,user:AdminUser,status:Literal['PENDING','APPROVED','REJECTED']|None=Query(None)):
    stmt=select(StaffApplication)
    if status:stmt=stmt.where(StaffApplication.status==status)
    rows=db.scalars(stmt.order_by(StaffApplication.created_at.desc())).all()
    return {'items':[public(r) for r in rows],'total':len(rows)}

@router.post('/staff-applications/{application_id}/review')
def review(application_id:str,payload:Review,db:DbSession,user:AdminUser):
    serialize_management(db,user)
    row=db.scalar(select(StaffApplication).where(StaffApplication.id==application_id).with_for_update().execution_options(populate_existing=True))
    if row is None:raise not_found('申请不存在。')
    desired='APPROVED' if payload.decision=='APPROVE' else 'REJECTED'
    if row.status!='PENDING':
        if row.status!=desired:raise conflict('申请已审核，请刷新。')
        if desired=='APPROVED' and payload.role and db.get(StaffUser,row.user_id).role!=payload.role:raise conflict('申请已审核为其他角色。')
        return public(row)
    if desired=='APPROVED':
        if db.scalar(select(StaffUser.id).where(func.lower(StaffUser.username)==row.username.lower())):raise conflict('该用户名不可用。')
        account=StaffUser(username=row.username,password_hash=row.password_hash,display_name=row.display_name,role=payload.role or row.requested_role,is_active=True)
        db.add(account);db.flush();row.user_id=account.id
    row.status=desired;row.reason=payload.reason;row.reviewed_by=user.id;row.reviewed_at=utcnow()
    db.commit();db.refresh(row)
    return public(row)

@router.get('/staff')
def staff(db:DbSession,user:AdminUser):
    rows=db.scalars(select(StaffUser).where(StaffUser.role.in_(['ADMIN','DOCTOR','NURSE'])).order_by(StaffUser.created_at)).all()
    return {'items':[StaffUserRead.model_validate(r) for r in rows],'total':len(rows)}

@router.patch('/staff/{staff_id}',response_model=StaffUserRead)
def patch_staff(staff_id:str,payload:StaffPatch,db:DbSession,user:AdminUser):
    serialize_management(db,user)
    row=db.scalar(select(StaffUser).where(StaffUser.id==staff_id,StaffUser.role.in_(['ADMIN','DOCTOR','NURSE'])).with_for_update().execution_options(populate_existing=True))
    if row is None:raise not_found('医护账号不存在。')
    role=payload.role or row.role;active=row.is_active if payload.is_active is None else payload.is_active
    if row.role=='ADMIN' and row.is_active and (role!='ADMIN' or not active):
        count=db.scalar(select(func.count()).select_from(StaffUser).where(StaffUser.role=='ADMIN',StaffUser.is_active.is_(True)))
        if count<=1:raise conflict('必须保留至少一个活跃管理员。')
    row.role=role;row.is_active=active;db.commit();db.refresh(row)
    return row
