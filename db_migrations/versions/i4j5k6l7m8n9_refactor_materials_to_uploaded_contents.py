"""refactor_materials_to_uploaded_contents

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-01-05 17:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i4j5k6l7m8n9'
down_revision: Union[str, Sequence[str], None] = 'h3i4j5k6l7m8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename materials table to uploaded_contents
    op.rename_table('materials', 'uploaded_contents')
    
    # 2. Extract assignment/material relationship data before modifying columns
    # We need to preserve the relationship defined by course_unit_id in the old materials table
    # This data will be moved to the new course_materials table
    
    # 3. Create course_materials table (The new "Application Layer" for materials)
    op.create_table(
        'course_materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('course_unit_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_visible', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=True),
        
        # Polymorphic association
        sa.Column('source_type', sa.String(50), nullable=False),  # 'uploaded_content', 'generated_content'
        sa.Column('source_id', sa.Integer(), nullable=False),
        
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 4. Migrate data: Create entries in course_materials for existing files
    # mapping old materials entries to new course_materials entries
    op.execute("""
        INSERT INTO course_materials 
        (course_id, course_unit_id, title, source_type, source_id, created_at)
        SELECT course_id, course_unit_id, file_name, 'uploaded_content', id, created_at
        FROM uploaded_contents
        WHERE course_unit_id IS NOT NULL
    """)
    
    # 5. Modify uploaded_contents table (The "Resource Pool")
    # Remove chapter binding - it's now a generic resource pool
    # Constraint name found via inspection: fk_materials_unit (renamed to uploaded_contents, but FK name persists usually)
    # However, since we renamed the table to uploaded_contents above, we should check if we refer to it by table name
    
    op.drop_constraint('fk_materials_unit', 'uploaded_contents', type_='foreignkey')
        
    op.drop_column('uploaded_contents', 'course_unit_id')
    
    # 6. Add Indexes
    op.create_index('idx_course_materials_unit', 'course_materials', ['course_unit_id'])
    op.create_index('idx_course_materials_source', 'course_materials', ['source_type', 'source_id'])
    
    # 7. Add Foreign Keys for course_materials
    op.create_foreign_key(
        'fk_course_materials_course', 'course_materials',
        'courses', ['course_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_course_materials_unit', 'course_materials',
        'course_units', ['course_unit_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    # 1. Add back course_unit_id to uploaded_contents
    op.add_column('uploaded_contents', sa.Column('course_unit_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'materials_course_unit_id_fkey', 'uploaded_contents',
        'course_units', ['course_unit_id'], ['id']
    )
    
    # 2. Restore data (best effort)
    # Update uploaded_contents.course_unit_id from course_materials
    op.execute("""
        UPDATE uploaded_contents uc
        SET course_unit_id = cm.course_unit_id
        FROM course_materials cm
        WHERE cm.source_type = 'uploaded_content' 
          AND cm.source_id = uc.id
    """)
    
    # 3. Drop course_materials table
    op.drop_table('course_materials')
    
    # 4. Rename back to materials
    op.rename_table('uploaded_contents', 'materials')
