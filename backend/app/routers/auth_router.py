"""
Authentication router: 完全依賴中央驗證服務 v4.0
支援：
1. Google 登入（透過中央驗證服務 - 先註冊後登入模式）
2. 不再同步至本地資料庫
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
import os
import httpx
from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()

# ==================== Central Auth Service Config ====================
AUTH_SERVICE_BASE_URL = os.getenv("AUTH_SERVICE_URL", "http://140.115.54.162:8500")
PUBLIC_KEY: Optional[str] = None  # 用於快取公鑰


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ==================== Pydantic Schemas ====================
class UserRole(str, Enum):
    student = "student"
    teacher = "teacher"


class GoogleRegisterRequest(BaseModel):
    """Google 使用者註冊請求（v4.0 流程）"""
    email: str = Field(..., description="Email (必須與 Google 帳號一致)")
    full_name: str = Field(..., description="中文姓名")
    identifier: str = Field(..., description="學號/教職員編號")
    department: Optional[str] = Field(None, description="系所/單位")
    role: UserRole = Field(default=UserRole.student, description="身分 (student/teacher)")


class GoogleRegisterResponse(BaseModel):
    """Google 註冊成功回應"""
    identifier: str
    full_name: str
    email: str
    role: str
    department: Optional[str] = None
    message: str = "註冊成功，請再次使用 Google 登入"


class GoogleLoginRequest(BaseModel):
    """Google 登入請求"""
    token: str = Field(..., description="Google 回傳的 credential token")


class GoogleLoginResponse(BaseModel):
    """Google 登入回應"""
    user_id: str
    full_name: str
    is_teacher: bool
    access_token: str
    email: Optional[str] = None
    department: Optional[str] = None
    identifier: Optional[str] = None
    message: str = "Google 登入成功"


# ==================== Helper Functions ====================
async def get_public_key() -> str:
    """取得或快取中央驗證服務的公鑰"""
    global PUBLIC_KEY
    if PUBLIC_KEY:
        return PUBLIC_KEY
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AUTH_SERVICE_BASE_URL}/api/auth/public-key")
        if resp.status_code != 200:
            raise HTTPException(status_code=503, detail="無法取得驗證公鑰")
        PUBLIC_KEY = resp.text
        return PUBLIC_KEY


# ==================== API Endpoints ====================

@router.get("/google/public-key")
async def get_google_public_key():
    """取得中央驗證服務公鑰（供前端或其他服務使用）"""
    try:
        key = await get_public_key()
        return {"public_key": key}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/register-google", response_model=GoogleRegisterResponse)
async def register_google_user(request: GoogleRegisterRequest):
    """
    Google 使用者註冊端點 (Central Auth v4.0)
    
    流程：
    1. 呼叫中央驗證服務 /register-direct 建立帳號
    2. 直接回傳中央驗證服務的結果（不寫入本地 DB）
    """
    # 呼叫中央驗證服務註冊
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{AUTH_SERVICE_BASE_URL}/api/auth/register-direct",
            json={
                "email": request.email,
                "full_name": request.full_name,
                "identifier": request.identifier,
                "department": request.department or "",
                "role": request.role.value
            }
        )
        
        if resp.status_code == 400:
            error_data = resp.json()
            raise HTTPException(status_code=400, detail=error_data.get("detail", "註冊失敗"))
        
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="中央驗證服務註冊失敗")
        
        central_user = resp.json()
    
    # 直接回傳結果（不同步至本地 DB）
    return GoogleRegisterResponse(
        identifier=central_user.get("identifier", request.identifier),
        full_name=central_user.get("full_name", request.full_name),
        email=central_user.get("email", request.email),
        role=central_user.get("role", request.role.value),
        department=central_user.get("department", request.department),
        message="註冊成功，請再次使用 Google 登入"
    )


@router.post("/google")
async def google_login(request: GoogleLoginRequest):
    """
    Google 登入端點 (Central Auth v4.0)
    
    流程：
    1. 將 Google Token 發送至中央驗證服務
    2. 若使用者不存在 (404 USER_NOT_FOUND)，回傳特殊錯誤供前端跳轉註冊
    3. 若成功，驗證 Token 並回傳使用者資訊（不同步至本地 DB）
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 1. 呼叫中央驗證服務
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Sending token to Central Auth Service: {AUTH_SERVICE_BASE_URL}/api/auth/google")
            resp = await client.post(
                f"{AUTH_SERVICE_BASE_URL}/api/auth/google",
                json={"token": request.token},
                headers={"Content-Type": "application/json"}
            )
            logger.info(f"Central Auth Service response: {resp.status_code}")
        except httpx.TimeoutException:
            raise HTTPException(status_code=503, detail="中央驗證服務逾時")
        except Exception as e:
            logger.error(f"Central Auth Service error: {str(e)}")
            raise HTTPException(status_code=503, detail=f"中央驗證服務連線失敗: {str(e)}")
        
        # 2. 處理 500 Internal Server Error
        if resp.status_code == 500:
            logger.error(f"Central Auth Service 500 error: {resp.text}")
            raise HTTPException(
                status_code=503, 
                detail="中央驗證服務內部錯誤，請稍後再試或聯繫管理員"
            )
        
        # 3. 處理 404 USER_NOT_FOUND
        if resp.status_code == 404:
            error_data = resp.json()
            detail = error_data.get("detail", {})
            
            # 檢查是否為 USER_NOT_FOUND 錯誤
            if isinstance(detail, dict) and detail.get("code") == "USER_NOT_FOUND":
                google_user = detail.get("google_user", {})
                return JSONResponse(
                    status_code=404,
                    content={
                        "code": "USER_NOT_FOUND",
                        "message": "請先完成註冊",
                        "google_user": {
                            "email": google_user.get("email", ""),
                            "name": google_user.get("name", ""),
                            "picture": google_user.get("picture", "")
                        }
                    }
                )
            else:
                raise HTTPException(status_code=404, detail="使用者不存在")
        
        if resp.status_code != 200:
            logger.error(f"Unexpected response: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=401, detail="Google 驗證失敗")
        
        data = resp.json()
        access_token = data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=401, detail="未取得 access_token")
    
    # 3. 驗證 Token 簽章
    try:
        public_key = await get_public_key()
        payload = jwt.decode(access_token, public_key, algorithms=["RS256"])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token 驗證失敗: {str(e)}")
    
    # 4. 解析 Payload（不同步至本地 DB）
    # 根據 v4.0 文件：sub=帳號, identifier=學號, full_name=姓名, role=身分
    user_id = payload.get("sub", "")
    identifier = payload.get("identifier", "")
    
    # 姓名處理
    raw_name = payload.get("full_name") or payload.get("name")
    if raw_name:
        full_name = raw_name
    else:
        email_for_name = payload.get("email", "")
        full_name = email_for_name.split("@")[0] if email_for_name else "未命名用戶"
    
    email = payload.get("email", "") or ""
    department = payload.get("department", "") or ""
    role = payload.get("role", "student") or "student"
    is_teacher = role == "teacher"
    
    return GoogleLoginResponse(
        user_id=user_id,
        full_name=full_name,
        is_teacher=is_teacher,
        access_token=access_token,
        email=email,
        department=department,
        identifier=identifier,
        message="Google 登入成功！"
    )
