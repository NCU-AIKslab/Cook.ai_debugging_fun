"""add_teacher_registration_and_approval_system

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-01-06 19:56:00.000000

詳細變更說明:
1. 修改資料表 'users': 新增 status, approved_at, approved_by 欄位（用於帳號審核機制）
2. 新增資料表 'teacher_profiles': 儲存教師專屬資料（機構、證明文件等）
3. 資料初始化: 在 'roles' 表中新增 'admin' 角色

設計說明:
- status 欄位預設為 'active'，學生註冊時自動啟用
- 教師註冊時 status='pending'，需管理員審核後改為 'active'
- teacher_profiles 與 student_profiles 對稱設計，使用 user_id 作為主鍵
- proof_document_url 為可選欄位，方便測試
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k6l7m8n9o0p1'
down_revision: Union[str, Sequence[str], None] = 'j5k6l7m8n9o0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # 1. 在 users 表新增審核相關欄位
    # - status: 帳號狀態 ('active', 'pending', 'rejected', 'suspended')
    # - approved_at: 審核通過時間
    # - approved_by: 審核者 ID (關聯到 users.id)
    op.add_column('users', sa.Column('status', sa.String(length=20), nullable=False, server_default='active'))
    op.add_column('users', sa.Column('approved_at', sa.TIMESTAMP(), nullable=True))
    op.add_column('users', sa.Column('approved_by', sa.Integer(), nullable=True))
    
    # 2. 建立 approved_by 的外鍵約束（關聯到 users.id）
    op.create_foreign_key(
        'fk_users_approved_by_users',
        'users',
        'users',
        ['approved_by'],
        ['id']
    )
    
    # 3. 建立 teacher_profiles 表（對應 student_profiles 的設計模式）
    # 此表用於儲存教師專屬資訊，欄位說明如下：
    # - user_id: 外鍵關聯到 users.id（主鍵）
    # - institution: 教師所屬機構/學校
    # - proof_document_url: 上傳的證明文件路徑（可選，測試時可不上傳）
    # - created_at: 建立時間
    # - updated_at: 更新時間
    op.create_table(
        'teacher_profiles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('institution', sa.String(length=255), nullable=False),
        sa.Column('proof_document_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # 4. 在 roles 表中新增 'admin' 角色
    # 使用 CASE WHEN 避免重複插入（若已存在則跳過）
    op.execute(
        """
        INSERT INTO roles (name)
        SELECT 'admin'
        WHERE NOT EXISTS (
            SELECT 1 FROM roles WHERE name = 'admin'
        )
        """
    )
    
    # 5. 建立索引以提升查詢效能
    op.create_index('idx_users_status', 'users', ['status'])
    op.create_index('idx_teacher_profiles_institution', 'teacher_profiles', ['institution'])


def downgrade() -> None:
    """Downgrade schema."""
    
    # 1. 刪除索引
    op.drop_index('idx_teacher_profiles_institution', 'teacher_profiles')
    op.drop_index('idx_users_status', 'users')
    
    # 2. 刪除 admin 角色
    op.execute("DELETE FROM roles WHERE name = 'admin'")
    
    # 3. 刪除 teacher_profiles 表
    op.drop_table('teacher_profiles')
    
    # 4. 刪除 users 表的外鍵約束
    op.drop_constraint('fk_users_approved_by_users', 'users', type_='foreignkey')
    
    # 5. 刪除 users 表新增的欄位
    op.drop_column('users', 'approved_by')
    op.drop_column('users', 'approved_at')
    op.drop_column('users', 'status')
