# -*- coding: utf-8 -*-
"""
Authentication router: Dual-track authentication system
Features:
1. Google login -> cooklogin_db.user (teacher needs Email approval)
2. Local login -> cookai.user_info (teacher needs backend manual approval)
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
import os
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jose import jwt, JWTError
from dotenv import load_dotenv
from sqlalchemy import select, insert, update
import logging

load_dotenv()

# ==================== Central Auth Service Config ====================
AUTH_SERVICE_BASE_URL = os.getenv("AUTH_SERVICE_URL", "http://140.115.54.162:8500")
PUBLIC_KEY: Optional[str] = None

# ==================== SMTP Config ====================
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
ADMIN_EMAIL = os.getenv("SMTP_USER", "pinyuanliu8@gmail.com")

# ==================== Database Import ====================
from backend.app.agents.debugging.db import (
    engine,
    get_cooklogin_engine,
    cooklogin_user_table,
    user_info_table,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


# ==================== Pydantic Schemas ====================
class UserRole(str, Enum):
    student = "student"
    teacher = "teacher"


class GoogleRegisterRequest(BaseModel):
    email: str = Field(..., description="Email")
    full_name: str = Field(..., description="Name")
    identifier: str = Field(..., description="Student ID or Name")
    department: Optional[str] = Field(None, description="Department")
    role: UserRole = Field(default=UserRole.student, description="Role")


class GoogleRegisterResponse(BaseModel):
    identifier: str
    full_name: str
    email: str
    role: str
    department: Optional[str] = None
    message: str = "Registration successful"


class GoogleLoginRequest(BaseModel):
    token: str = Field(..., description="Google credential token")


class GoogleLoginResponse(BaseModel):
    user_id: str
    full_name: str
    is_teacher: bool
    access_token: str
    email: Optional[str] = None
    department: Optional[str] = None
    identifier: Optional[str] = None
    message: str = "Google login successful"


class LocalRegisterRequest(BaseModel):
    stu_id: str = Field(..., description="Student ID")
    stu_name: str = Field(..., description="Name")
    stu_pwd: str = Field(..., description="Password")
    role: UserRole = Field(default=UserRole.student, description="Role")


class LocalRegisterResponse(BaseModel):
    stu_id: str
    stu_name: str
    is_teacher: bool
    message: str


class LocalLoginRequest(BaseModel):
    stu_id: str = Field(..., description="Student ID")
    stu_pwd: str = Field(..., description="Password")


class LocalLoginResponse(BaseModel):
    stu_id: str
    stu_name: str
    is_teacher: bool
    message: str


# ==================== Helper Functions ====================
async def get_public_key() -> str:
    global PUBLIC_KEY
    if PUBLIC_KEY:
        return PUBLIC_KEY
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AUTH_SERVICE_BASE_URL}/api/auth/public-key")
        if resp.status_code != 200:
            raise HTTPException(status_code=503, detail="Cannot get public key")
        PUBLIC_KEY = resp.text
        return PUBLIC_KEY


def send_email(to_email: str, subject: str, body_html: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        
        part = MIMEText(body_html, "html", "utf-8")
        msg.attach(part)
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_teacher_approval_request(teacher_name: str, teacher_email: str, department: str):
    subject = f"[Cook.ai] Teacher Account Approval - {teacher_name}"
    # Use email in URL instead of user_id for reliability
    import urllib.parse
    encoded_email = urllib.parse.quote(teacher_email)
    approval_link = f"http://cookai-debugging-lab.moocs.tw:8000/api/auth/approve-teacher?email={encoded_email}"
    
    body = f"""
    <html>
    <body>
        <h2>New Teacher Registration</h2>
        <p><strong>Name:</strong> {teacher_name}</p>
        <p><strong>Email:</strong> {teacher_email}</p>
        <p><strong>Department:</strong> {department or 'Not provided'}</p>
        <hr>
        <p>Click the link below to approve:</p>
        <a href="{approval_link}">{approval_link}</a>
    </body>
    </html>
    """
    send_email(ADMIN_EMAIL, subject, body)


def send_teacher_approved_notification(teacher_email: str, teacher_name: str):
    subject = "[Cook.ai] Your Teacher Account is Approved"
    body = f"""
    <html>
    <body>
        <h2>Account Approved</h2>
        <p>Dear {teacher_name},</p>
        <p>Your Cook.ai teacher account has been approved. You can now login.</p>
        <p>Login URL: <a href="http://cookai-debugging-lab.moocs.tw:3001">http://cookai-debugging-lab.moocs.tw:3001</a></p>
        <hr>
        <p>Cook.ai Team</p>
    </body>
    </html>
    """
    send_email(teacher_email, subject, body)


# ==================== Google Login Endpoints (cooklogin_db) ====================

@router.get("/google/public-key")
async def get_google_public_key():
    try:
        key = await get_public_key()
        return {"public_key": key}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/register-google", response_model=GoogleRegisterResponse)
async def register_google_user(request: GoogleRegisterRequest):
    """Google user registration -> cooklogin_db.user"""
    is_teacher = request.role == UserRole.teacher
    
    # 1. Call central auth service
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
            raise HTTPException(status_code=400, detail=error_data.get("detail", "Registration failed"))
        
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Central auth service error")
    
    # 2. Sync to cooklogin_db.users
    try:
        cooklogin_engine = get_cooklogin_engine()
        with cooklogin_engine.begin() as conn:
            existing = conn.execute(
                select(cooklogin_user_table).where(cooklogin_user_table.c.email == request.email)
            ).fetchone()
            
            if existing:
                conn.execute(
                    update(cooklogin_user_table).where(cooklogin_user_table.c.email == request.email).values(
                        full_name=request.full_name,
                        username=request.identifier,  # Update username to identifier
                        identifier=request.identifier,
                        role=request.role.value,
                        department=request.department or "",
                        verified=not is_teacher
                    )
                )
                user_id = existing._mapping["id"]
            else:
                result = conn.execute(
                    insert(cooklogin_user_table).values(
                        email=request.email,
                        full_name=request.full_name,
                        username=request.identifier,  # Use identifier as username
                        identifier=request.identifier,
                        role=request.role.value,
                        department=request.department or "",
                        verified=not is_teacher
                    ).returning(cooklogin_user_table.c.id)
                )
                user_id = result.fetchone()[0]
                logger.info(f"Successfully wrote user to cooklogin_db, user_id={user_id}")
    except Exception as e:
        logger.error(f"Failed to sync to cooklogin_db: {e}")
        user_id = None
    
    # 3. Teacher needs approval - send Email (even if DB failed)
    if is_teacher:
        logger.info(f"Teacher registration detected: {request.email}, user_id={user_id}")
        try:
            send_teacher_approval_request(
                request.full_name, 
                request.email, 
                request.department or ""
            )
            logger.info(f"Approval email sent to admin for {request.email}")
        except Exception as e:
            logger.error(f"Failed to send approval email: {e}")
        
        return GoogleRegisterResponse(
            identifier=request.identifier,
            full_name=request.full_name,
            email=request.email,
            role=request.role.value,
            department=request.department,
            message="Registration successful. Your account requires admin approval. You will receive an email when approved."
        )
    
    return GoogleRegisterResponse(
        identifier=request.identifier,
        full_name=request.full_name,
        email=request.email,
        role=request.role.value,
        department=request.department,
        message="Registration successful. Please login with Google."
    )


@router.post("/google")
async def google_login(request: GoogleLoginRequest):
    """Google login -> check cooklogin_db.user"""
    # 1. Call central auth service
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{AUTH_SERVICE_BASE_URL}/api/auth/google",
                json={"token": request.token},
                headers={"Content-Type": "application/json"}
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=503, detail="Central auth service timeout")
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Central auth service error: {str(e)}")
        
        if resp.status_code == 500:
            raise HTTPException(status_code=503, detail="Central auth service internal error")
        
        # 404 USER_NOT_FOUND
        if resp.status_code == 404:
            error_data = resp.json()
            detail = error_data.get("detail", {})
            
            if isinstance(detail, dict) and detail.get("code") == "USER_NOT_FOUND":
                google_user = detail.get("google_user", {})
                return JSONResponse(
                    status_code=404,
                    content={
                        "code": "USER_NOT_FOUND",
                        "message": "Please complete registration first",
                        "google_user": {
                            "email": google_user.get("email", ""),
                            "name": google_user.get("name", ""),
                            "picture": google_user.get("picture", "")
                        }
                    }
                )
            else:
                raise HTTPException(status_code=404, detail="User not found")
        
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Google authentication failed")
        
        data = resp.json()
        access_token = data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=401, detail="No access_token received")
    
    # 2. Verify Token
    try:
        public_key = await get_public_key()
        payload = jwt.decode(access_token, public_key, algorithms=["RS256"])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")
    
    # 3. Parse Payload
    user_id = payload.get("sub", "")
    identifier = payload.get("identifier", "")
    email = payload.get("email", "")
    full_name = payload.get("full_name") or payload.get("name") or email.split("@")[0]
    department = payload.get("department", "")
    role = payload.get("role", "student")
    is_teacher = role == "teacher"
    
    # 4. MANDATORY: Check cooklogin_db verification status (for teachers)
    if is_teacher:
        try:
            cooklogin_engine = get_cooklogin_engine()
            with cooklogin_engine.connect() as conn:
                local_user = conn.execute(
                    select(cooklogin_user_table).where(cooklogin_user_table.c.email == email)
                ).fetchone()
                
                # Teacher MUST exist in cooklogin_db
                if not local_user:
                    raise HTTPException(
                        status_code=403, 
                        detail="Teacher account not found. Please complete registration first."
                    )
                
                # Teacher MUST be verified
                if not local_user._mapping["verified"]:
                    raise HTTPException(
                        status_code=403, 
                        detail="Your teacher account is pending admin verification. Please wait for approval email."
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to check cooklogin_db verification: {e}")
            raise HTTPException(
                status_code=503, 
                detail="Unable to verify teacher status. Please try again later."
            )
    
    return GoogleLoginResponse(
        user_id=user_id,
        full_name=full_name,
        is_teacher=is_teacher,
        access_token=access_token,
        email=email,
        department=department,
        identifier=identifier,
        message="Google login successful!"
    )


@router.get("/approve-teacher")
async def approve_teacher(email: str):
    """Approve teacher account by email and send notification"""
    import urllib.parse
    decoded_email = urllib.parse.unquote(email)
    logger.info(f"Approving teacher: {decoded_email}")
    
    try:
        cooklogin_engine = get_cooklogin_engine()
        with cooklogin_engine.connect() as conn:
            user = conn.execute(
                select(cooklogin_user_table).where(cooklogin_user_table.c.email == decoded_email)
            ).fetchone()
            
            if not user:
                raise HTTPException(status_code=404, detail=f"User not found: {decoded_email}")
            
            user_data = user._mapping
            
            if user_data["verified"]:
                return {"message": "Account already approved"}
        
        with cooklogin_engine.begin() as conn:
            conn.execute(
                update(cooklogin_user_table).where(cooklogin_user_table.c.email == decoded_email).values(
                    verified=True
                )
            )
        
        # Send notification email to teacher
        send_teacher_approved_notification(decoded_email, user_data["full_name"])
        
        return {"message": f"Successfully approved {user_data['full_name']}'s teacher account. Notification email sent to {decoded_email}."}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve teacher: {e}")
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve teacher: {e}")
        raise HTTPException(status_code=500, detail="Approval failed")


# ==================== Local Login Endpoints (cookai.user_info) ====================

@router.post("/register", response_model=LocalRegisterResponse)
async def register_local_user(request: LocalRegisterRequest):
    """Local registration -> cookai.user_info"""
    is_teacher = request.role == UserRole.teacher
    
    # 1. Check if exists
    with engine.connect() as conn:
        existing = conn.execute(
            select(user_info_table).where(user_info_table.c.stu_id == request.stu_id)
        ).fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail="Student ID already registered")
    
    # 2. Create account (plaintext password for compatibility)
    try:
        with engine.begin() as conn:
            conn.execute(
                insert(user_info_table).values(
                    stu_id=request.stu_id,
                    stu_name=request.stu_name,
                    stu_pwd=request.stu_pwd,
                    semester="114-1",  # Default semester
                    is_teacher=False  # Teacher needs manual backend approval
                )
            )
    except Exception as e:
        logger.error(f"Failed to create local user: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")
    
    # 3. Teacher needs backend approval
    if is_teacher:
        return LocalRegisterResponse(
            stu_id=request.stu_id,
            stu_name=request.stu_name,
            is_teacher=False,
            message="Registration successful! Teacher role requires backend approval."
        )
    
    return LocalRegisterResponse(
        stu_id=request.stu_id,
        stu_name=request.stu_name,
        is_teacher=False,
        message="Registration successful! You can now login."
    )


@router.post("/login", response_model=LocalLoginResponse)
async def login_local_user(request: LocalLoginRequest):
    """Local login -> cookai.user_info"""
    # 1. Find user
    with engine.connect() as conn:
        user = conn.execute(
            select(user_info_table).where(user_info_table.c.stu_id == request.stu_id)
        ).fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user_data = user._mapping
    
    # 2. Verify password (plaintext comparison)
    if user_data["stu_pwd"] != request.stu_pwd:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    
    # 3. Return login result
    # Explicitly check is_teacher boolean (handle None/Null as False)
    is_teacher_val = user_data.get("is_teacher")
    is_teacher = bool(is_teacher_val) if is_teacher_val is not None else False
    
    logger.info(f"Local login: user={user_data.get('stu_id')}, is_teacher_db={is_teacher_val}, final={is_teacher}")
    
    return LocalLoginResponse(
        stu_id=user_data["stu_id"],
        stu_name=user_data["stu_name"],
        is_teacher=is_teacher,
        message="Login successful!"
    )
