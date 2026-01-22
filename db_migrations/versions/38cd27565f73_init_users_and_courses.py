"""init_users_and_courses

Revision ID: 38cd27565f73
Revises: 
Create Date: 2025-11-07 20:27:01.467590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '38cd27565f73'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 建立 USERS 表 (Minimal)
    op.execute("""
    CREATE TABLE USERS (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        full_name VARCHAR(100),
        role_id INTEGER, -- 暫時允許 NULL 且不設 FK
        created_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        last_login_time TIMESTAMPTZ
    );
    """)
    
    # 2. 建立 COURSES 表 (Minimal)
    op.execute("""
    CREATE TABLE COURSES (
        id SERIAL PRIMARY KEY,
        teacher_id INTEGER, -- 暫時允許 NULL 且不設 FK
        semester_name VARCHAR(100),
        name VARCHAR(255) NOT NULL,
        description TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 3. 插入「研究員」資料
    op.execute("""
    INSERT INTO USERS (email, full_name)
    VALUES ('monicachen0331@gmail.com', '陳淳瑜');
    """)
    
    # 4. 插入「實驗課程」資料
    op.execute("""
    INSERT INTO COURSES (name, semester_name)
    VALUES ('創意學習', '1141');
    """)
    
    # 5. 加入「待辦事項」註解
    op.execute("COMMENT ON COLUMN USERS.role_id IS 'TODO: 應設定為 FK，關聯至 ROLES.id';")
    op.execute("COMMENT ON COLUMN COURSES.teacher_id IS 'TODO: 應設定為 FK，關聯至 USERS.id';")
    


def downgrade() -> None:
    
    op.execute("DROP TABLE IF EXISTS COURSES;")
    op.execute("DROP TABLE IF EXISTS USERS;")
