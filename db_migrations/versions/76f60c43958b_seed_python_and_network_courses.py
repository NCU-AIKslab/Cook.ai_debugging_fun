"""seed_python_and_network_courses

Revision ID: 76f60c43958b
Revises: bba2365818e8
Create Date: 2025-12-09 13:49:34.395137

詳細變更說明:
1. 資料初始化 (Seed Data): 在 'courses' 表中建立課程 '程式設計-Python'。
2. 資料初始化 (Seed Data): 在 'courses' 表中建立課程 '智慧型網路服務工程'。

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = '76f60c43958b'
down_revision: Union[str, Sequence[str], None] = 'bba2365818e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 取得資料庫連線
    connection = op.get_bind()
    
    # 1. 查詢 testTeacher 的 user_id
    result = connection.execute(
        sa.text("SELECT id FROM users WHERE email = 'testTeacher@gmail.com'")
    )
    teacher_user_id = result.fetchone()[0]
    
    # 2. 在 'courses' 表中建立課程 '程式設計-Python'
    connection.execute(
        sa.text("""
            INSERT INTO courses (teacher_id, semester_name, name, description, created_at)
            VALUES (:teacher_id, :semester_name, :name, :description, :created_at)
        """),
        {
            'teacher_id': teacher_user_id,
            'semester_name': '1142',
            'name': '程式設計-Python',
            'description': '程式設計-Python課程',
            'created_at': datetime.now()
        }
    )
    
    # 3. 在 'courses' 表中建立課程 '智慧型網路服務工程'
    connection.execute(
        sa.text("""
            INSERT INTO courses (teacher_id, semester_name, name, description, created_at)
            VALUES (:teacher_id, :semester_name, :name, :description, :created_at)
        """),
        {
            'teacher_id': teacher_user_id,
            'semester_name': '1142',
            'name': '智慧型網路服務工程',
            'description': '智慧型網路服務工程課程',
            'created_at': datetime.now()
        }
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 取得資料庫連線
    connection = op.get_bind()
    
    # 刪除新增的課程
    connection.execute(
        sa.text("DELETE FROM courses WHERE name IN ('程式設計-Python', '智慧型網路服務工程')")
    )
