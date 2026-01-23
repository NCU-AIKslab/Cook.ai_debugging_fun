"""
Authentication router: 簡化版 - 使用 debugging.user_info 表
學生可自行註冊（學號、姓名、密碼），使用學號和密碼登入
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, MetaData, Table, Column, String, Boolean, select, insert
import os
from dotenv import load_dotenv

load_dotenv()

# ==================== Database Setup ====================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

engine = create_engine(DATABASE_URL)
metadata = MetaData()

# 定義 user_info 表
user_info_table = Table(
    "user_info",
    metadata,
    Column("stu_id", String, primary_key=True),
    Column("stu_name", String, nullable=False),
    Column("stu_pwd", String, nullable=False),
    Column("semester", String),
    Column("is_teacher", Boolean, default=False),
    schema="debugging",
    extend_existing=True,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ==================== Pydantic Schemas ====================
class RegisterRequest(BaseModel):
    """學生註冊請求"""
    stu_id: str = Field(..., min_length=1, description="學號")
    stu_name: str = Field(..., min_length=1, description="姓名")
    stu_pwd: str = Field(..., min_length=1, description="密碼")


class RegisterResponse(BaseModel):
    """註冊成功回應"""
    stu_id: str
    stu_name: str
    message: str = "註冊成功"


class LoginRequest(BaseModel):
    """登入請求"""
    stu_id: str = Field(..., description="學號")
    stu_pwd: str = Field(..., description="密碼")


class LoginResponse(BaseModel):
    """登入成功回應"""
    stu_id: str
    stu_name: str
    message: str = "登入成功"


# ==================== API Endpoints ====================

@router.post("/register", response_model=RegisterResponse)
async def register_student(request: RegisterRequest):
    """
    學生註冊端點
    
    流程：
    1. 檢查學號是否已註冊
    2. 建立 user_info 記錄（密碼不加密）
    """
    with engine.connect() as conn:
        # 1. 檢查學號是否已存在
        existing = conn.execute(
            select(user_info_table.c.stu_id).where(
                user_info_table.c.stu_id == request.stu_id
            )
        ).fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail="此學號已註冊")
        
        # 2. 新增使用者記錄
        conn.execute(
            insert(user_info_table).values(
                stu_id=request.stu_id,
                stu_name=request.stu_name,
                stu_pwd=request.stu_pwd,
                semester="114-1",
                is_teacher=False
            )
        )
        conn.commit()
    
    return RegisterResponse(
        stu_id=request.stu_id,
        stu_name=request.stu_name,
        message="註冊成功！"
    )


@router.post("/login", response_model=LoginResponse)
async def login_student(request: LoginRequest):
    """
    學生登入端點
    
    流程：
    1. 根據學號查詢使用者
    2. 驗證密碼（明文比對）
    3. 返回使用者資訊
    """
    with engine.connect() as conn:
        # 查詢使用者
        row = conn.execute(
            select(
                user_info_table.c.stu_id,
                user_info_table.c.stu_name,
                user_info_table.c.stu_pwd
            ).where(user_info_table.c.stu_id == request.stu_id)
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=401, detail="學號不存在")
        
        row_mapping = row._mapping if hasattr(row, "_mapping") else row
        
        # 驗證密碼（明文比對）
        if row_mapping["stu_pwd"] != request.stu_pwd:
            raise HTTPException(status_code=401, detail="密碼錯誤")
        
        return LoginResponse(
            stu_id=row_mapping["stu_id"],
            stu_name=row_mapping["stu_name"],
            message="登入成功！"
        )
