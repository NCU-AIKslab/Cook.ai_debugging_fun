"""add_topic_id_to_course_units

Revision ID: f1a2b3c4d5e6
Revises: acfe2cfc333b
Create Date: 2026-01-05 16:28:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Rename week -> topic_id
    op.alter_column('course_units', 'week', new_column_name='topic_id')
    
    # Step 2: Rename chapter_name -> name
    op.alter_column('course_units', 'chapter_name', new_column_name='name')
    
    # Step 3: Add description column
    op.add_column('course_units', sa.Column('description', sa.Text(), nullable=True))
    
    # Step 4: Drop display_order column (User requested removal)
    op.drop_column('course_units', 'display_order')
    
    # Step 5: Add updated_at timestamp
    op.add_column('course_units',
        sa.Column('updated_at',
                  sa.DateTime(),
                  server_default=sa.func.now(),
                  onupdate=sa.func.now(),
                  nullable=True)
    )
    
    # Step 6: Add indexes
    op.create_index('idx_course_units_topic_id', 'course_units', ['topic_id'])
    op.create_index('idx_course_units_course_id', 'course_units', ['course_id'])


def downgrade() -> None:
    # Remove indexes and columns
    op.drop_index('idx_course_units_course_id', 'course_units')
    op.drop_index('idx_course_units_topic_id', 'course_units')
    op.drop_column('course_units', 'updated_at')
    
    # Restore display_order
    op.add_column('course_units', sa.Column('display_order', sa.Integer(), nullable=True))
    
    # Remove description
    op.drop_column('course_units', 'description')
    
    # Restore column names
    op.alter_column('course_units', 'name', new_column_name='chapter_name')
    op.alter_column('course_units', 'topic_id', new_column_name='week')
