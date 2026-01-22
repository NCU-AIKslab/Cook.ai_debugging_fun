"""
Teacher Course Router: 整合教師與課程相關的 API
處理課程管理、單元管理、公告管理以及教師課程列表
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import Table, text
from backend.app.utils.db_logger import engine, metadata

logger = logging.getLogger(__name__)

# 建立 Router (不設定統一 prefix，因為要處理 /api/courses 和 /api/teachers)
router = APIRouter()

# 反射資料表 (保留供參考或未來使用)
try:
    courses_table = Table('courses', metadata, autoload_with=engine)
    course_units_table = Table('course_units', metadata, autoload_with=engine)
    users_table = Table('users', metadata, autoload_with=engine)
except Exception as e:
    print(f"Error reflecting course tables: {e}")

# ==================== Pydantic Schemas ====================

class CourseResponse(BaseModel):
    """一般課程回應"""
    id: int
    name: str
    semester: str  # 統一欄位名稱 (原 semester_name)
    description: Optional[str] = None
    teacher_name: str

class CourseUnitResponse(BaseModel):
    """課程單元回應"""
    id: int
    topic_id: Optional[int] = 0
    name: str
    description: Optional[str] = None

class CourseDetailResponse(BaseModel):
    """課程詳情回應（含單元）"""
    id: int
    name: str
    semester: str # 統一欄位名稱
    description: Optional[str] = None
    teacher_name: str
    units: List[CourseUnitResponse]

class AnnouncementCreate(BaseModel):
    """建立公告的請求"""
    title: str
    content: str

class AnnouncementResponse(BaseModel):
    """公告回應"""
    id: int
    title: str
    content: str
    is_pinned: bool
    created_at: str
    author_name: str

class UnitCreate(BaseModel):
    """建立課程單元的請求"""
    topic_id: int
    name: str
    description: Optional[str] = None

# ==================== API Endpoints (Courses) ====================

@router.get("/api/courses", response_model=List[CourseResponse], tags=["Courses"])
async def get_all_courses():
    """
    取得所有課程列表
    """
    with engine.connect() as conn:
        query = text("""
            SELECT c.id, c.name, c.semester_name, c.description, u.full_name as teacher_name
            FROM courses c
            LEFT JOIN users u ON c.teacher_id = u.id
            ORDER BY c.created_at DESC
        """)
        result = conn.execute(query)
        
        courses = []
        for row in result:
            courses.append(CourseResponse(
                id=row[0],
                name=row[1],
                semester=row[2],
                description=row[3],
                teacher_name=row[4] or "未知教師"
            ))
        
        return courses

class CourseCreate(BaseModel):
    """建立課程請求"""
    name: str
    semester_name: str
    description: Optional[str] = None
    teacher_id: int

@router.post("/api/courses", response_model=CourseResponse, tags=["Courses"])
async def create_course(course: CourseCreate):
    """
    建立新課程
    """
    with engine.connect() as conn:
        # 1. 確認教師存在
        user_check = conn.execute(
            text("SELECT id FROM users WHERE id = :user_id"), 
            {"user_id": course.teacher_id}
        ).fetchone()
        
        if not user_check:
            raise HTTPException(status_code=404, detail="教師不存在")

        # 2. 插入課程
        insert_query = text("""
            INSERT INTO courses (name, semester_name, description, teacher_id, created_at)
            VALUES (:name, :semester_name, :description, :teacher_id, NOW() AT TIME ZONE 'Asia/Taipei')
            RETURNING id, name, semester_name, description
        """)
        result = conn.execute(insert_query, {
            "name": course.name,
            "semester_name": course.semester_name,
            "description": course.description or "",
            "teacher_id": course.teacher_id
        })
        conn.commit()
        row = result.fetchone()
        
        # 3. 创建默认章节 "課堂簡介"
        default_unit_query = text("""
            INSERT INTO course_units (course_id, topic_id, name, description)
            VALUES (:course_id, 1, '課堂簡介', '本章節為課程簡介，教師可自行修改內容')
        """)
        conn.execute(default_unit_query, {"course_id": row[0]})
        conn.commit()
        
        # 4. 取得教師名稱
        teacher_name_query = text("SELECT full_name FROM users WHERE id = :id")
        teacher_name_res = conn.execute(teacher_name_query, {"id": course.teacher_id}).fetchone()
        teacher_name = teacher_name_res[0] if teacher_name_res else "未知教師"

        return CourseResponse(
            id=row[0],
            name=row[1],
            semester=row[2],
            description=row[3],
            teacher_name=teacher_name
        )

@router.get("/api/courses/{course_id}", response_model=CourseDetailResponse, tags=["Courses"])
async def get_course_detail(course_id: int):
    """
    取得單一課程詳情（含週次單元）
    """
    with engine.connect() as conn:
        course_query = text("""
            SELECT c.id, c.name, c.semester_name, c.description, u.full_name as teacher_name
            FROM courses c
            LEFT JOIN users u ON c.teacher_id = u.id
            WHERE c.id = :course_id
        """)
        course_result = conn.execute(course_query, {"course_id": course_id}).fetchone()
        
        if not course_result:
            raise HTTPException(status_code=404, detail="課程不存在")
        
        units_query = text("""
            SELECT id, topic_id, name, description
            FROM course_units
            WHERE course_id = :course_id
            ORDER BY topic_id ASC
        """)
        units_result = conn.execute(units_query, {"course_id": course_id})
        
        units = []
        for row in units_result:
            units.append(CourseUnitResponse(
                id=row[0],
                topic_id=row[1],
                name=row[2],
                description=row[3]
            ))
        
        return CourseDetailResponse(
            id=course_result[0],
            name=course_result[1],
            semester=course_result[2],
            description=course_result[3],
            teacher_name=course_result[4] or "未知教師",
            units=units
        )

@router.get("/api/courses/{course_id}/units", response_model=List[CourseUnitResponse], tags=["Courses"])
async def get_course_units(course_id: int):
    """
    取得課程的所有週次單元
    """
    with engine.connect() as conn:
        course_check = conn.execute(
            text("SELECT id FROM courses WHERE id = :course_id"),
            {"course_id": course_id}
        ).fetchone()
        
        if not course_check:
            raise HTTPException(status_code=404, detail="課程不存在")
        
        query = text("""
            SELECT id, topic_id, name, description
            FROM course_units
            WHERE course_id = :course_id
            ORDER BY topic_id ASC
        """)
        result = conn.execute(query, {"course_id": course_id})
        
        units = []
        for row in result:
            units.append(CourseUnitResponse(
                id=row[0],
                topic_id=row[1],
                name=row[2],
                description=row[3]
            ))
        
        return units

@router.post("/api/courses/{course_id}/units", response_model=CourseUnitResponse, tags=["Courses"])
async def create_course_unit(course_id: int, unit: UnitCreate):
    """
    建立新課程單元
    """
    with engine.connect() as conn:
        course_check = conn.execute(
            text("SELECT id FROM courses WHERE id = :course_id"),
            {"course_id": course_id}
        ).fetchone()
        
        if not course_check:
            raise HTTPException(status_code=404, detail="課程不存在")
        
        insert_query = text("""
            INSERT INTO course_units (course_id, topic_id, name, description, updated_at)
            VALUES (:course_id, :topic_id, :name, :description, NOW() AT TIME ZONE 'Asia/Taipei')
            RETURNING id, topic_id, name
        """)
        result = conn.execute(insert_query, {
            "course_id": course_id,
            "topic_id": unit.topic_id,
            "name": unit.name,
            "description": unit.description or ""
        })
        conn.commit()
        
        row = result.fetchone()
        
        logger.info(f"✅ Successfully created course unit: ID={row[0]}, Topic={row[1]}, Name='{row[2]}', Course={course_id}")
        
        return CourseUnitResponse(
            id=row[0],
            topic_id=row[1],
            name=row[2],
            description=None
        )

@router.delete("/api/courses/{course_id}/units/{unit_id}", tags=["Courses"])
async def delete_course_unit(course_id: int, unit_id: int):
    """
    刪除課程單元
    """
    with engine.connect() as conn:
        check_query = text("""
            SELECT id FROM course_units 
            WHERE id = :unit_id AND course_id = :course_id
        """)
        unit = conn.execute(check_query, {
            "unit_id": unit_id,
            "course_id": course_id
        }).fetchone()
        
        if not unit:
            raise HTTPException(status_code=404, detail="課程單元不存在")
        
        delete_query = text("DELETE FROM course_units WHERE id = :unit_id")
        conn.execute(delete_query, {"unit_id": unit_id})
        conn.commit()
        
        return {"message": "課程單元已刪除"}

# ==================== Announcements ====================

@router.get("/api/courses/{course_id}/announcements", response_model=List[AnnouncementResponse], tags=["Courses"])
async def get_course_announcements(course_id: int):
    """
    取得課程的所有公告
    """
    with engine.connect() as conn:
        query = text("""
            SELECT a.id, a.title, a.content, a.is_pinned, a.created_at, u.full_name
            FROM course_announcements a
            LEFT JOIN users u ON a.author_id = u.id
            WHERE a.course_id = :course_id
            ORDER BY a.is_pinned DESC, a.created_at DESC
        """)
        result = conn.execute(query, {"course_id": course_id})
        
        announcements = []
        for row in result:
            announcements.append(AnnouncementResponse(
                id=row[0],
                title=row[1],
                content=row[2],
                is_pinned=row[3],
                created_at=row[4].strftime("%Y-%m-%d") if row[4] else "",
                author_name=row[5] or "未知"
            ))
        
        return announcements

@router.post("/api/courses/{course_id}/announcements", response_model=AnnouncementResponse, tags=["Courses"])
async def create_announcement(course_id: int, announcement: AnnouncementCreate):
    """
    建立新公告
    """
    with engine.connect() as conn:
        course_check = conn.execute(
            text("SELECT id FROM courses WHERE id = :course_id"),
            {"course_id": course_id}
        ).fetchone()
        
        if not course_check:
            raise HTTPException(status_code=404, detail="課程不存在")
        
        teacher_query = text("SELECT teacher_id FROM courses WHERE id = :course_id")
        teacher_result = conn.execute(teacher_query, {"course_id": course_id}).fetchone()
        author_id = teacher_result[0] if teacher_result else 1
        
        insert_query = text("""
            INSERT INTO course_announcements (course_id, author_id, title, content, is_pinned, created_at, updated_at)
            VALUES (:course_id, :author_id, :title, :content, :is_pinned, NOW() AT TIME ZONE 'Asia/Taipei', NOW() AT TIME ZONE 'Asia/Taipei')
            RETURNING id, title, content, is_pinned, created_at
        """)
        result = conn.execute(insert_query, {
            "course_id": course_id,
            "author_id": author_id,
            "title": announcement.title,
            "content": announcement.content,
            "is_pinned": False
        })
        conn.commit()
        
        row = result.fetchone()
        
        author_query = text("SELECT full_name FROM users WHERE id = :author_id")
        author_result = conn.execute(author_query, {"author_id": author_id}).fetchone()
        
        logger.info(f"✅ Successfully created announcement: ID={row[0]}, Title='{row[1]}', Course={course_id}")
        
        return AnnouncementResponse(
            id=row[0],
            title=row[1],
            content=row[2],
            is_pinned=row[3],
            created_at=row[4].strftime("%Y-%m-%d"),
            author_name=author_result[0] if author_result else "未知"
        )

@router.delete("/api/courses/{course_id}/announcements/{announcement_id}", tags=["Courses"])
async def delete_announcement(course_id: int, announcement_id: int):
    """
    刪除公告
    """
    with engine.connect() as conn:
        check_query = text("""
            SELECT id FROM course_announcements 
            WHERE id = :announcement_id AND course_id = :course_id
        """)
        announcement = conn.execute(check_query, {
            "announcement_id": announcement_id,
            "course_id": course_id
        }).fetchone()
        
        if not announcement:
            raise HTTPException(status_code=404, detail="公告不存在")
        
        delete_query = text("DELETE FROM course_announcements WHERE id = :announcement_id")
        conn.execute(delete_query, {"announcement_id": announcement_id})
        conn.commit()
        
        return {"message": "公告已刪除"}

# ==================== API Endpoints (Teachers) ====================

@router.get("/api/teachers/{teacher_id}/courses", response_model=List[CourseResponse], tags=["Teachers"])
async def get_teacher_courses(teacher_id: int):
    """
    取得特定教師開設的所有課程列表
    """
    with engine.connect() as conn:
        query = text("""
            SELECT c.id, c.name, c.semester_name, c.description, u.full_name as teacher_name
            FROM courses c
            LEFT JOIN users u ON c.teacher_id = u.id
            WHERE c.teacher_id = :teacher_id
            ORDER BY c.created_at DESC
        """)
        result = conn.execute(query, {"teacher_id": teacher_id})
        
        courses = []
        for row in result:
            courses.append(CourseResponse(
                id=row[0],
                name=row[1],
                semester=row[2],
                description=row[3],
                teacher_name=row[4] or "未知教師"
            ))
        
        return courses
