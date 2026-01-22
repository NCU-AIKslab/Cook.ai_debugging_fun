"""create_assignments_tables

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-01-05 16:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'h3i4j5k6l7m8'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create assignments table with polymorphic source design
    op.create_table(
        'assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('course_unit_id', sa.Integer(), nullable=True),  # NULL if spanning multiple units
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('assignment_timing', sa.String(50), nullable=True),  # 'pre_class', 'post_class'
        sa.Column('due_date', sa.DateTime(), nullable=True),
        
        # Polymorphic association to content source
        sa.Column('source_type', sa.String(50), nullable=False),  # 'material', 'generated_content'
        sa.Column('source_id', sa.Integer(), nullable=False),  # materials.id or generated_contents.id
        
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create assignment_attachments table
    op.create_table(
        'assignment_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create submissions table
    op.create_table(
        'submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('grade', sa.Numeric(5, 2), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create submission_attachments table
    op.create_table(
        'submission_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add foreign keys
    op.create_foreign_key(
        'fk_assignments_course_id',
        'assignments', 'courses',
        ['course_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_assignments_course_unit_id',
        'assignments', 'course_units',
        ['course_unit_id'], ['id'],
        ondelete='SET NULL'
    )
    
    op.create_foreign_key(
        'fk_assignments_author_id',
        'assignments', 'users',
        ['author_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_assignment_attachments_assignment_id',
        'assignment_attachments', 'assignments',
        ['assignment_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_submissions_assignment_id',
        'submissions', 'assignments',
        ['assignment_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_submissions_user_id',
        'submissions', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_submission_attachments_submission_id',
        'submission_attachments', 'submissions',
        ['submission_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Add indexes
    op.create_index('idx_assignments_course_id', 'assignments', ['course_id'])
    op.create_index('idx_assignments_course_unit_id', 'assignments', ['course_unit_id'])
    op.create_index('idx_assignments_author_id', 'assignments', ['author_id'])
    op.create_index('idx_assignments_source', 'assignments', ['source_type', 'source_id'])  # Polymorphic index
    op.create_index('idx_submissions_assignment_id', 'submissions', ['assignment_id'])
    op.create_index('idx_submissions_user_id', 'submissions', ['user_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('submission_attachments')
    op.drop_table('submissions')
    op.drop_table('assignment_attachments')
    op.drop_table('assignments')
