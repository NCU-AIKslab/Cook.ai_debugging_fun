"""add_email_verification_and_update_student_profiles

Revision ID: e8f9a0b1c2d3
Revises: db7352f76a08
Create Date: 2025-12-28 21:35:00.000000

詳細變更說明:
1. 新增資料表 'email_verifications': 儲存 Email 驗證碼資訊
2. 修改資料表 'student_profiles': 移除 enrollment_year 欄位，將 major 改為 NOT NULL
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, Sequence[str], None] = 'db7352f76a08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # 1. 建立 email_verifications 表
    # 此表用於儲存 Email 驗證資訊，各欄位說明如下：
    # - id: 主鍵，自動遞增的唯一識別碼
    # - email: 儲存待驗證的電子郵件地址
    # - code: 儲存發送給使用者的 6 位數驗證碼
    # - created_at: 紀錄驗證碼產生的時間，預設為資料庫當前時間
    # - expires_at: 紀錄驗證碼的失效時間，用於驗證是否過期
    # - is_used: 標記該驗證碼是否已被使用過，預設為 False
    op.create_table(
        'email_verifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=6), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 2. 建立索引以提升查詢效能
    op.create_index('idx_email_verifications_email', 'email_verifications', ['email'])
    op.create_index('idx_email_verifications_expires_at', 'email_verifications', ['expires_at'])
    
    # 3. 更新 student_profiles 表中 major 為 NULL 的記錄
    # 將 NULL 值設為預設值，避免 NOT NULL 約束失敗
    op.execute(
        """
        UPDATE student_profiles 
        SET major = '未指定' 
        WHERE major IS NULL
        """
    )
    
    # 4. 將 student_profiles.major 改為 NOT NULL
    op.alter_column(
        'student_profiles',
        'major',
        existing_type=sa.String(length=100),
        nullable=False
    )
    
    # 5. 移除 student_profiles.enrollment_year 欄位
    op.drop_column('student_profiles', 'enrollment_year')


def downgrade() -> None:
    """Downgrade schema."""
    
    # 1. 恢復 student_profiles.enrollment_year 欄位
    op.add_column(
        'student_profiles',
        sa.Column('enrollment_year', sa.Integer(), nullable=True)
    )
    
    # 2. 將 student_profiles.major 改回 NULLABLE
    op.alter_column(
        'student_profiles',
        'major',
        existing_type=sa.String(length=100),
        nullable=True
    )
    
    # 3. 刪除索引
    op.drop_index('idx_email_verifications_expires_at', 'email_verifications')
    op.drop_index('idx_email_verifications_email', 'email_verifications')
    
    # 4. 刪除 email_verifications 表
    op.drop_table('email_verifications')
