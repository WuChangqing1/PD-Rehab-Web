"""Permission checked documentation. Public documents need no staff session."""
from fastapi import APIRouter,Request
from fastapi.responses import FileResponse
from app.api.deps import DbSession,get_current_user,_bearer
from app.core.errors import APIError,ErrorCode
from app.services.document_library import documents

router=APIRouter(prefix='/documents',tags=['documents'])

async def role_for(request,db):
    credentials=await _bearer(request)
    if credentials:return get_current_user(db,request,credentials).role
    return 'PUBLIC'

def load(document_id,role):
    try:return documents.read(document_id,role)
    except KeyError:raise APIError(404,ErrorCode.NOT_FOUND,'文档不存在或尚未发布。')
    except PermissionError:raise APIError(401 if role=='PUBLIC' else 403,ErrorCode.FORBIDDEN,'请使用有权访问此文档的账号登录。')

@router.get('')
async def list_documents(request:Request,db:DbSession):
    return {'documents':documents.list(await role_for(request,db))}

@router.get('/{document_id}')
async def read_document(document_id:str,request:Request,db:DbSession):
    return load(document_id,await role_for(request,db))

@router.get('/{document_id}/file')
async def document_file(document_id:str,request:Request,db:DbSession):
    role=await role_for(request,db);d=load(document_id,role)
    return FileResponse(documents.path(d['path']),media_type='application/pdf' if d['format']=='pdf' else 'text/markdown',
                        headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; frame-ancestors 'self'"})

@router.get('/{document_id}/assets/{name:path}')
async def document_asset(document_id:str,name:str,request:Request,db:DbSession):
    role=await role_for(request,db);load(document_id,role)
    try:p=documents.asset(document_id,name,role)
    except (KeyError,ValueError):raise APIError(404,ErrorCode.NOT_FOUND,'附件未发布。')
    return FileResponse(p,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
