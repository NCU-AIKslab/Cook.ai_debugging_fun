"""add_error_message_to_orchestration_jobs

Revision ID: b649d64cbd8b
Revises: af43c8bf9d6e
Create Date: 2025-11-08 18:08:10.536662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b649d64cbd8b'
down_revision: Union[str, Sequence[str], None] = 'af43c8bf9d6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print("--- [Cook.ai] Adding 'error_message' column to 'orchestration_jobs' ---")
    op.add_column('orchestration_jobs', sa.Column('error_message', sa.Text(), nullable=True))
    print("--- [Cook.ai] 'error_message' column added successfully ---")



def downgrade() -> None:
    print("--- [Cook.ai] Dropping 'error_message' column from 'orchestration_jobs' ---")
    op.drop_column('orchestration_jobs', 'error_message')
    print("--- [Cook.ai] 'error_message' column dropped ---")
    
