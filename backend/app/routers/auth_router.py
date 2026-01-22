"""
Authentication router: 處理使用者註冊、登入等功能
"""
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
import os
import uuid
from pathlib import Path
from passlib.context import CryptContext
from sqlalchemy import Table, select, insert, delete
from datetime import datetime, timedelta
from backend.app.utils.db_logger import engine, metadata
from backend.app.constants.departments import ALL_DEPARTMENTS
from backend.app.utils.email_service import generate_verification_code, send_verification_email

# 建立 Router
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# 密碼加密設定 - 使用 Argon2（更安全，無長度限制）
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# 反射資料表
try:
    users_table = Table('users', metadata, autoload_with=engine)
    roles_table = Table('roles', metadata, autoload_with=engine)
    user_authentications_table = Table('user_authentications', metadata, autoload_with=engine)
    student_profiles_table = Table('student_profiles', metadata, autoload_with=engine)
    teacher_profiles_table = Table('teacher_profiles', metadata, autoload_with=engine)
    email_verifications_table = Table('email_verifications', metadata, autoload_with=engine)
except Exception as e:
    print(f"Error reflecting authentication tables: {e}")

# ==================== Pydantic Schemas ====================

class RegisterRequest(BaseModel):
    """註冊請求"""
    email: EmailStr = Field(..., description="使用者 Email")
    password: str = Field(..., min_length=6, description="使用者密碼 (至少 6 個字元)")
    full_name: str = Field(..., min_length=1, max_length=100, description="使用者姓名")
    student_id: str = Field(..., min_length=1, max_length=100, description="學號 (必填)")
    role: str = Field("student", description="使用者角色: teacher, student, TA (預設: student)")
    major: str = Field(..., max_length=100, description="科系 (必填)")
    
    @field_validator('major')
    @classmethod
    def validate_major(cls, v: str) -> str:
        """檢查科系是否在允許清單中"""
        if v not in ALL_DEPARTMENTS:
            raise ValueError(f'無效的科系: {v}')
        return v


class RegisterResponse(BaseModel):
    """註冊成功回應"""
    user_id: int
    email: str
    full_name: str
    role: str
    message: str = "註冊成功"


class SendVerificationCodeRequest(BaseModel):
    """發送驗證碼請求"""
    email: EmailStr = Field(..., description="要驗證的 Email")


class SendVerificationCodeResponse(BaseModel):
    """發送驗證碼回應"""
    message: str
    expires_in_minutes: int = 10


class VerifyCodeRequest(BaseModel):
    """驗證驗證碼請求"""
    email: EmailStr = Field(..., description="Email")
    code: str = Field(..., min_length=6, max_length=6, description="6 位數驗證碼")


class VerifyCodeResponse(BaseModel):
    """驗證驗證碼回應"""
    verified: bool
    message: str


class LoginRequest(BaseModel):
    """登入請求"""
    email: EmailStr = Field(..., description="使用者 Email")
    password: str = Field(..., min_length=6, description="使用者密碼")


class LoginResponse(BaseModel):
    """登入成功回應"""
    user_id: int
    email: str
    full_name: str
    role: str
    message: str = "登入成功"


# ==================== Helper Functions ====================

def hash_password(password: str) -> str:
    """將明文密碼加密"""
    return pwd_context.hash(password)


def get_role_id(role_name: str) -> Optional[int]:
    """根據角色名稱取得 role_id"""
    with engine.connect() as conn:
        query = select(roles_table.c.id).where(roles_table.c.name == role_name)
        result = conn.execute(query).fetchone()
        return result[0] if result else None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """驗證密碼是否正確"""
    return pwd_context.verify(plain_password, hashed_password)


# ==================== API Endpoints ====================

@router.post("/send-verification-code", response_model=SendVerificationCodeResponse)
async def send_verification_code(request: SendVerificationCodeRequest):
    """
    發送驗證碼到指定 Email
    
    流程：
    1. 生成 6 位數驗證碼
    2. 儲存到資料庫 (有效期 10 分鐘)
    3. 發送郵件
    """
    with engine.connect() as conn:
        # 生成驗證碼
        code = generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=10)
        
        # 刪除該 Email 的舊驗證碼
        delete_stmt = delete(email_verifications_table).where(
            email_verifications_table.c.email == request.email
        )
        conn.execute(delete_stmt)
        
        # 插入新驗證碼
        insert_stmt = insert(email_verifications_table).values(
            email=request.email,
            code=code,
            expires_at=expires_at,
            is_used=False
        )
        conn.execute(insert_stmt)
        conn.commit()
        
        # 發送郵件
        success = send_verification_email(request.email, code)
        
        if not success:
            raise HTTPException(status_code=500, detail="發送驗證碼失敗，請稍後再試")
        
        return SendVerificationCodeResponse(
            message="驗證碼已發送至您的信箱",
            expires_in_minutes=10
        )


@router.post("/verify-code", response_model=VerifyCodeResponse)
async def verify_code(request: VerifyCodeRequest):
    """
    驗證驗證碼是否正確
    
    流程：
    1. 檢查驗證碼是否存在且未過期
    2. 檢查是否已使用
    3. 標記為已使用
    """
    with engine.connect() as conn:
        # 查詢驗證碼
        query = select(email_verifications_table).where(
            (email_verifications_table.c.email == request.email) &
            (email_verifications_table.c.code == request.code) &
            (email_verifications_table.c.is_used == False) &
            (email_verifications_table.c.expires_at > datetime.now())
        )
        result = conn.execute(query).fetchone()
        
        if not result:
            return VerifyCodeResponse(
                verified=False,
                message="驗證碼錯誤或已過期"
            )
        
        # 標記為已使用
        from sqlalchemy import update
        update_stmt = update(email_verifications_table).where(
            (email_verifications_table.c.email == request.email) &
            (email_verifications_table.c.code == request.code)
        ).values(is_used=True)
        conn.execute(update_stmt)
        conn.commit()
        
        return VerifyCodeResponse(
            verified=True,
            message="驗證成功"
        )


@router.post("/register", response_model=RegisterResponse)
async def register_user(request: RegisterRequest):
    """
    使用者註冊端點
    
    流程：
    1. 檢查 Email 和 Full Name 配對是否已存在（防止重複註冊）
    2. 驗證角色是否有效
    3. 建立 users 記錄
    4. 建立 user_authentications 記錄 (加密密碼)
    5. 建立 student_profiles 記錄 (student_id 和 major 都是必填)
    """
    
    with engine.connect() as conn:
        # 1. 檢查 Email 和 Full Name 配對是否已存在（防止重複註冊）
        existing_user = conn.execute(
            select(users_table).where(
                (users_table.c.email == request.email) & 
                (users_table.c.full_name == request.full_name)
            )
        ).fetchone()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="此帳號已被註冊（Email 和姓名配對已存在）")
        
        # 2. 取得 role_id
        role_id = get_role_id(request.role)
        if not role_id:
            raise HTTPException(status_code=400, detail=f"無效的角色: {request.role}")
        
        # 3. 建立 users 記錄（學生預設為 active 狀態）
        user_insert = insert(users_table).values(
            email=request.email,
            full_name=request.full_name,
            role_id=role_id,
            status='active'  # 學生註冊立即啟用
        )
        result = conn.execute(user_insert)
        user_id = result.inserted_primary_key[0]
        
        # 4. 建立 user_authentications 記錄
        hashed_password = hash_password(request.password)
        auth_insert = insert(user_authentications_table).values(
            user_id=user_id,
            provider="local",
            password=hashed_password
        )
        conn.execute(auth_insert)
        
        # 5. 建立 student_profiles 記錄（student_id 現在是必填）
        # 檢查學號是否重複
        existing_student = conn.execute(
            select(student_profiles_table).where(
                student_profiles_table.c.student_id == request.student_id
            )
        ).fetchone()
        
        if existing_student:
            conn.rollback()
            raise HTTPException(status_code=400, detail="此學號已被註冊")
        
        profile_insert = insert(student_profiles_table).values(
            user_id=user_id,
            student_id=request.student_id,
            major=request.major
        )
        conn.execute(profile_insert)
        
        # 提交事務
        conn.commit()
        
        return RegisterResponse(
            user_id=user_id,
            email=request.email,
            full_name=request.full_name,
            role=request.role
        )


# ==================== 教師註冊端點 ====================

@router.post("/register/teacher")
async def register_teacher(
    email: str = Form(...),
    password: str = Form(min_length=6),
    full_name: str = Form(...),
    institution: str = Form(...),
    proof_document: UploadFile = File(None)
):
    """
    教師註冊端點
    
    流程：
    1. 檢查 Email 是否已註冊
    2. 建立 users 記錄 (status='pending')
    3. 建立 user_authentications 記錄
    4. 儲存證明文件（如果有）
    5. 建立 teacher_profiles 記錄
    """
    
    with engine.connect() as conn:
        # 1. 檢查 Email 是否已註冊
        existing_user = conn.execute(
            select(users_table).where(users_table.c.email == email)
        ).fetchone()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="此 Email 已被註冊")
        
        # 2. 取得 teacher role_id (應該是 1)
        role_id = get_role_id("teacher")
        if not role_id:
            raise HTTPException(status_code=400, detail="無效的角色")
        
        # 3. 建立 users 記錄 (status='pending'，需等待審核)
        user_insert = insert(users_table).values(
            email=email,
            full_name=full_name,
            role_id=role_id,
            status='pending'  # 教師需要審核
        )
        result = conn.execute(user_insert)
        user_id = result.inserted_primary_key[0]
        
        # 4. 建立 user_authentications 記錄
        hashed_password = hash_password(password)
        auth_insert = insert(user_authentications_table).values(
            user_id=user_id,
            provider="local",
            password=hashed_password
        )
        conn.execute(auth_insert)
        
        # 5. 儲存證明文件（如果有）
        proof_url = None
        if proof_document and proof_document.filename:
            # 建立上傳目錄
            upload_dir = Path("uploads/proof_documents")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成唯一檔名
            file_ext = Path(proof_document.filename).suffix
            file_name = f"user_{user_id}_{uuid.uuid4()}{file_ext}"
            file_path = upload_dir / file_name
            
            # 儲存檔案
            content = await proof_document.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            proof_url = str(file_path)
        
        # 6. 建立 teacher_profiles 記錄
        profile_insert = insert(teacher_profiles_table).values(
            user_id=user_id,
            institution=institution,
            proof_document_url=proof_url
        )
        conn.execute(profile_insert)
        
        # 提交事務
        conn.commit()
        
        return {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "role": "teacher",
            "status": "pending",
            "message": "註冊申請已送出，管理員將在 1-3 個工作天內完成審核。"
        }


@router.post("/login", response_model=LoginResponse)
async def login_user(request: LoginRequest):
    """
    使用者登入端點
    
    流程：
    1. 根據 Email 查詢使用者
    2. 驗證密碼
    3. 返回使用者資訊
    """
    with engine.connect() as conn:
        # 查詢使用者（包含 status）
        user_query = select(
            users_table.c.id,
            users_table.c.email,
            users_table.c.full_name,
            users_table.c.role_id,
            users_table.c.status
        ).where(users_table.c.email == request.email)
        
        user_result = conn.execute(user_query).fetchone()
        
        if not user_result:
            raise HTTPException(status_code=401, detail="Email 或密碼錯誤")
        
        user_id, email, full_name, role_id, status = user_result
        
        # 檢查帳號狀態
        if status == 'pending':
            raise HTTPException(
                status_code=403,
                detail="您的帳號尚未通過審核，請耐心等待管理員處理。"
            )
        elif status == 'rejected':
            raise HTTPException(
                status_code=403,
                detail="您的申請已被拒絕，請聯繫管理員瞭解詳情。"
            )
        elif status == 'suspended':
            raise HTTPException(
                status_code=403,
                detail="您的帳號已被停權，請聯繫管理員。"
            )
        
        # 查詢密碼
        auth_query = select(user_authentications_table.c.password).where(
            (user_authentications_table.c.user_id == user_id) &
            (user_authentications_table.c.provider == "local")
        )
        auth_result = conn.execute(auth_query).fetchone()
        
        if not auth_result:
            raise HTTPException(status_code=401, detail="Email 或密碼錯誤")
        
        hashed_password = auth_result[0]
        
        # 驗證密碼
        if not verify_password(request.password, hashed_password):
            raise HTTPException(status_code=401, detail="Email 或密碼錯誤")
        
        # 查詢角色名稱
        role_query = select(roles_table.c.name).where(roles_table.c.id == role_id)
        role_result = conn.execute(role_query).fetchone()
        role_name = role_result[0] if role_result else "student"
        
        return LoginResponse(
            user_id=user_id,
            email=email,
            full_name=full_name,
            role=role_name
        )
