"""add_timestamps_to_materials_table

Revision ID: acfe2cfc333b
Revises: 1240827742bf
Create Date: 2025-11-08 21:38:02.725257

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'acfe2cfc333b'
down_revision: Union[str, Sequence[str], None] = '1240827742bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 為 'materials' 表新增 created_at 欄位
    op.add_column('materials', 
        sa.Column('created_at', 
                  sa.DateTime(), 
                  server_default=sa.func.now(), 
                  nullable=True) # 設為 True 以避免舊資料出錯
    )
    
    # 為 'materials' 表新增 updated_at 欄位
    op.add_column('materials', 
        sa.Column('updated_at', 
                  sa.DateTime(), 
                  server_default=sa.func.now(), 
                  onupdate=sa.func.now(), 
                  nullable=True) # 設為 True 以避免舊資料出錯
    )


def downgrade() -> None:
    op.drop_column('materials', 'updated_at')
    op.drop_column('materials', 'created_at')
