"""add_auth_tables

Revision ID: d145b8eadb40
Revises: a1b2c3d4e5f6
Create Date: 2025-11-28 14:38:30.008752

詳細變更說明:
1. 新增資料表 'roles': 儲存使用者角色 (如 teacher, student, TA)。
2. 新增資料表 'user_authentications': 儲存驗證資訊 (密碼、提供者)。
3. 新增資料表 'student_profiles': 儲存學生專屬資料 (學號、科系等)。
4. 修改資料表 'users': 為 'role_id' 欄位加上 Foreign Key，關聯至 'roles.id'。
5. 資料初始化 (Seed Data): 在 'roles' 表中預先插入 'teacher', 'student', 'TA' 三種角色。

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd145b8eadb40'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 在資料庫中建立 ROLES 表格
    roles = op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # 2. 在 ROLES 表中插入初始資料 teacher, student, TA 三種角色
    op.bulk_insert(roles,
        [
            {'name': 'teacher'},
            {'name': 'student'},
            {'name': 'TA'}
        ]
    )

    # 3. 在資料庫中建立 USER_AUTHENTICATIONS 表格
    op.create_table(
        'user_authentications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], )
    )

    # 4. 在資料庫中建立 STUDENT_PROFILES 表格
    op.create_table(
        'student_profiles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.String(length=100), nullable=False),
        sa.Column('major', sa.String(length=100), nullable=True),
        sa.Column('enrollment_year', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.UniqueConstraint('student_id')
    )

    # 5. 加入 USERS table FK to ROLES table
    op.create_foreign_key(
        'fk_users_role_id_roles', 'users', 'roles', ['role_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 1. 刪除 USERS 表的 FK 約束
    op.drop_constraint('fk_users_role_id_roles', 'users', type_='foreignkey')

    # 2. 刪除 STUDENT_PROFILES 表格
    op.drop_table('student_profiles')

    # 3. 刪除 USER_AUTHENTICATIONS 表格
    op.drop_table('user_authentications')

    # 4. 刪除 ROLES 表格
    op.drop_table('roles')
