"""seed_test_teacher_and_ai_course

Revision ID: bba2365818e8
Revises: d145b8eadb40
Create Date: 2025-12-08 16:00:00.000000

詳細變更說明:
1. 資料初始化 (Seed Data): 在 'users' 表中建立測試教師帳號 'testTeacher'。
2. 資料初始化 (Seed Data): 在 'user_authentications' 表中建立 testTeacher 的驗證資訊。
3. 資料初始化 (Seed Data): 在 'courses' 表中建立課程 '人工智慧教育應用概論'。
4. 資料初始化 (Seed Data): 在 'course_units' 表中建立 16 週的課程單元。

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Integer, Text
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = 'bba2365818e8'
down_revision: Union[str, Sequence[str], None] = 'd145b8eadb40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 加密後的密碼 (testTeacher)
HASHED_PASSWORD = '$argon2id$v=19$m=65536,t=3,p=4$JsRYKwVgbO3d+/9/L4VQSg$AsvRkjqrm0+YDo+S/faFwqP4SDa2HNF4864xTOKr5cU'


def upgrade() -> None:
    """Upgrade schema."""
    # 取得資料庫連線
    connection = op.get_bind()
    
    # 1. 查詢 teacher 角色的 role_id
    result = connection.execute(
        sa.text("SELECT id FROM roles WHERE name = 'teacher'")
    )
    teacher_role_id = result.fetchone()[0]
    
    # 2. 在 'users' 表中建立測試教師帳號 'testTeacher'
    connection.execute(
        sa.text("""
            INSERT INTO users (email, full_name, role_id, created_time)
            VALUES (:email, :full_name, :role_id, :created_time)
        """),
        {
            'email': 'testTeacher@gmail.com',
            'full_name': 'testTeacher',
            'role_id': teacher_role_id,
            'created_time': datetime.now()
        }
    )
    
    # 3. 查詢剛建立的 testTeacher 的 user_id
    result = connection.execute(
        sa.text("SELECT id FROM users WHERE email = 'testTeacher@gmail.com'")
    )
    teacher_user_id = result.fetchone()[0]
    
    # 4. 在 'user_authentications' 表中建立 testTeacher 的驗證資訊
    connection.execute(
        sa.text("""
            INSERT INTO user_authentications (user_id, provider, password)
            VALUES (:user_id, :provider, :password)
        """),
        {
            'user_id': teacher_user_id,
            'provider': 'local',
            'password': HASHED_PASSWORD
        }
    )
    
    # 5. 在 'courses' 表中建立課程 '人工智慧教育應用概論'
    connection.execute(
        sa.text("""
            INSERT INTO courses (teacher_id, semester_name, name, description, created_at)
            VALUES (:teacher_id, :semester_name, :name, :description, :created_at)
        """),
        {
            'teacher_id': teacher_user_id,
            'semester_name': '1142',
            'name': '人工智慧教育應用概論',
            'description': '人工智慧教育應用概論課程',
            'created_at': datetime.now()
        }
    )
    
    # 6. 查詢剛建立的課程 course_id
    result = connection.execute(
        sa.text("SELECT id FROM courses WHERE name = '人工智慧教育應用概論' AND teacher_id = :teacher_id"),
        {'teacher_id': teacher_user_id}
    )
    course_id = result.fetchone()[0]
    
    # 7. 在 'course_units' 表中建立 16 週的課程單元
    course_units = [
        {'week': 1, 'display_order': 1, 'chapter_name': '課程簡介'},
        {'week': 2, 'display_order': 2, 'chapter_name': '機器學習-監督式學習演算法'},
        {'week': 3, 'display_order': 3, 'chapter_name': '機器學習-非監督式學習演算法'},
        {'week': 4, 'display_order': 4, 'chapter_name': '深度學習-多層感知器(MLP)'},
        {'week': 5, 'display_order': 5, 'chapter_name': '深度學習-遞歸神經網路(RNN)'},
        {'week': 6, 'display_order': 6, 'chapter_name': '深度學習-卷積神經網路(CNN)'},
        {'week': 7, 'display_order': 7, 'chapter_name': '深度學習-生成對抗神經網路(GAN)'},
        {'week': 8, 'display_order': 8, 'chapter_name': '期中心得報告'},
        {'week': 9, 'display_order': 9, 'chapter_name': '人工智慧教育應用案例 (1)'},
        {'week': 10, 'display_order': 10, 'chapter_name': '人工智慧教育應用案例 (2)'},
        {'week': 11, 'display_order': 11, 'chapter_name': '人工智慧教育應用案例 (3)'},
        {'week': 12, 'display_order': 12, 'chapter_name': '人工智慧教育應用案例 (4)'},
        {'week': 13, 'display_order': 13, 'chapter_name': '期末小組報告 (I)'},
        {'week': 14, 'display_order': 14, 'chapter_name': '期末小組報告 (II)'},
        {'week': 15, 'display_order': 15, 'chapter_name': '期末小組報告 (III)'},
        {'week': 16, 'display_order': 16, 'chapter_name': '期末心得報告'},
    ]
    
    for unit in course_units:
        connection.execute(
            sa.text("""
                INSERT INTO course_units (course_id, chapter_name, week, display_order)
                VALUES (:course_id, :chapter_name, :week, :display_order)
            """),
            {
                'course_id': course_id,
                'chapter_name': unit['chapter_name'],
                'week': unit['week'],
                'display_order': unit['display_order']
            }
        )


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()
    
    # 1. 查詢 testTeacher 的 user_id
    result = connection.execute(
        sa.text("SELECT id FROM users WHERE email = 'testTeacher@gmail.com'")
    )
    row = result.fetchone()
    
    if row:
        teacher_user_id = row[0]
        
        # 2. 查詢並刪除該教師的課程單元
        result = connection.execute(
            sa.text("SELECT id FROM courses WHERE teacher_id = :teacher_id"),
            {'teacher_id': teacher_user_id}
        )
        course_row = result.fetchone()
        
        if course_row:
            course_id = course_row[0]
            # 3. 刪除 'course_units' 表中的課程單元
            connection.execute(
                sa.text("DELETE FROM course_units WHERE course_id = :course_id"),
                {'course_id': course_id}
            )
        
        # 4. 刪除 'courses' 表中的課程
        connection.execute(
            sa.text("DELETE FROM courses WHERE teacher_id = :teacher_id"),
            {'teacher_id': teacher_user_id}
        )
        
        # 5. 刪除 'user_authentications' 表中的驗證資訊
        connection.execute(
            sa.text("DELETE FROM user_authentications WHERE user_id = :user_id"),
            {'user_id': teacher_user_id}
        )
        
        # 6. 刪除 'users' 表中的測試教師帳號
        connection.execute(
            sa.text("DELETE FROM users WHERE id = :user_id"),
            {'user_id': teacher_user_id}
        )
