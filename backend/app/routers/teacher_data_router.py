"""
Teacher Data Router: 處理教師端教材資料管理功能

此 router 包含：
1. 取得教材列表 (get_materials)
2. 更新教材名稱 (update_material_name)
3. 文件匯入處理 (ingest_document)
"""
import os
import shutil
import tempfile
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from sqlalchemy import Table, select, update

from backend.app.agents.teacher_agent.ingestion import process_file
from backend.app.utils.db_logger import engine, metadata

# Create router
router = APIRouter(prefix="/api/v1", tags=["Teacher Data Management"])

# --- Reflect 'uploaded_contents' table ---
try:
    uploaded_contents_table = Table('uploaded_contents', metadata, autoload_with=engine)
except Exception as e:
    print(f"Error reflecting 'uploaded_contents' table: {e}")
    uploaded_contents_table = None

# --- Pydantic Models ---

class Material(BaseModel):
    id: int
    name: str = Field(alias='file_name')
    unique_content_id: int

class UpdateMaterialRequest(BaseModel):
    name: str

class IngestResponse(BaseModel):
    unique_content_id: int
    file_name: str
    message: str

# --- Data Management Endpoints ---

@router.get("/materials", response_model=List[Material])
async def get_materials(course_id: int):
    """
    Endpoint to get all materials for a given course.
    """
    if uploaded_contents_table is None:
        raise HTTPException(status_code=500, detail="Database table 'uploaded_contents' not found.")
    query = select(uploaded_contents_table).where(uploaded_contents_table.c.course_id == course_id)
    try:
        with engine.connect() as conn:
            result = conn.execute(query)
            rows = result.fetchall()
            material_list = [{"id": row.id, "file_name": row.file_name, "unique_content_id": row.unique_content_id} for row in rows]
            return material_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

@router.patch("/materials/{material_id}", status_code=204)
async def update_material_name(material_id: int, request: UpdateMaterialRequest):
    """
    Endpoint to update the name of a material.
    """
    if uploaded_contents_table is None:
        raise HTTPException(status_code=500, detail="Database table 'uploaded_contents' not found.")
    stmt = update(uploaded_contents_table).where(uploaded_contents_table.c.id == material_id).values(file_name=request.name)
    try:
        with engine.connect() as conn:
            result = conn.execute(stmt)
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Material with id {material_id} not found.")
            conn.commit()
        return
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database update failed: {e}")

@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    course_id: int = Form(1), 
    uploader_id: int = Form(1), 
    force_reprocess: bool = Form(False),
    url: Optional[str] = Form(None),  # ✅ 新增：URL 參數
    file: Optional[UploadFile] = File(None)  # ✅ 修改為可選
):
    """
    Endpoint to ingest a document from file upload or URL.
    
    Args:
        course_id: ID of the course
        uploader_id: ID of the uploader
        force_reprocess: If True, reprocess even if file already exists
        url: Optional URL for web content (if provided, file is ignored)
        file: Optional file to ingest (required if url is not provided)
    """
    # 驗證：必須提供 file 或 url 其中之一
    if not file and not url:
        raise HTTPException(
            status_code=400, 
            detail="Either 'file' or 'url' must be provided"
        )
    
    if url:
        # 處理 URL（web loader）
        unique_content_id, was_skipped = await run_in_threadpool(
            process_file,
            file_path=url,  # web loader 會識別這是 URL
            uploader_id=uploader_id,
            course_id=course_id,
            force_reprocess=force_reprocess
        )
        
        if unique_content_id is None:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to process URL '{url}'. Check server logs for details."
            )
        
        # 建立顯示用的檔案名稱
        file_name = url.split('/')[-1] or 'web_content.html'
        if '?' in file_name:
            file_name = file_name.split('?')[0]
        if not file_name.endswith('.html'):
            file_name += '.html'
        
        # ✅ 根據 was_skipped 返回不同消息
        if was_skipped:
            message = f"此網址內容已存在(ID: {unique_content_id})，不重複匯入"
        else:
            message = f"成功匯入網址 '{url}'"
        
        return IngestResponse(
            unique_content_id=unique_content_id,
            file_name=file_name,
            message=message
        )
    
    else:
        # 處理檔案上傳（原有邏輯）
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            unique_content_id, was_skipped = await run_in_threadpool(
                process_file,
                file_path=file_path,
                uploader_id=uploader_id,
                course_id=course_id,
                force_reprocess=force_reprocess
            )
        
        if unique_content_id is None:
            raise HTTPException(status_code=500, detail="Failed to process the document.")
        
        # ✅ 根據 was_skipped 返回不同消息
        if was_skipped:
            message = f"此檔案已存在(ID: {unique_content_id})，不重複匯入"
        else:
            message = f"成功匯入檔案 '{file.filename}'"
        
        return IngestResponse(
            unique_content_id=unique_content_id,
            file_name=file.filename,
            message=message
        )
