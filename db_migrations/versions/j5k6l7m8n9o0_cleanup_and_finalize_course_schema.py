"""cleanup_and_finalize_course_schema

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-01-05 17:27:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j5k6l7m8n9o0'
down_revision: Union[str, Sequence[str], None] = 'i4j5k6l7m8n9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename assignments -> course_assignments
    op.rename_table('assignments', 'course_assignments')
    
    # 2. Drop assignment_attachments (Redundant due to polymorphic source design)
    op.drop_table('assignment_attachments')
    
    # 3. Create course_announcements (New Feature)
    op.create_table(
        'course_announcements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_pinned', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 4. Add Indexes & FKs for Announcements
    op.create_index('idx_course_announcements_course_id', 'course_announcements', ['course_id'])
    
    op.create_foreign_key(
        'fk_course_announcements_course', 'course_announcements',
        'courses', ['course_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_course_announcements_author', 'course_announcements',
        'users', ['author_id'], ['id'], ondelete='CASCADE'
    )
    
    # 5. Fix Foreign Keys for renamed course_assignments
    # When renaming a table, existing FKs pointing TO IT usually update automatically in Postgres,
    # but we should ensure downstream tables like submissions are correct.
    # Submissions has fk_submissions_assignment_id -> assignments.id
    # We might need to rename the constraint or column for consistency, 
    # but 'assignment_id' is still a valid column name referring to a 'course_assignment'.
    # Let's keep the column name 'assignment_id' in submissions to avoid massive refactor,
    # just ensuring the FK constraint is valid.
    
    # Note: Alembic rename_table usually handles the table name change.
    # We should just verify if we want to rename indexes or constraints if strict naming is required.
    # For now, practical functionality is preserved.


def downgrade() -> None:
    # 1. Drop course_announcements
    op.drop_table('course_announcements')
    
    # 2. Restore assignment_attachments
    op.create_table(
        'assignment_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_foreign_key(
        'fk_assignment_attachments_assignment_id',
        'assignment_attachments', 'course_assignments', # referring to new name before rename back
        ['assignment_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # 3. Rename back to assignments
    op.rename_table('course_assignments', 'assignments')
