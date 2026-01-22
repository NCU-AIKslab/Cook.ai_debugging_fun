"""improve task_evaluations schema

Revision ID: a1b2c3d4e5f6
Revises: 6f71973b4903
Create Date: 2025-11-21 19:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '6f71973b4903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print("--- [Cook.ai] UPGRADE: Improving TASK_EVALUATIONS schema ---")
    
    # 1. Add new columns
    print("Adding columns: job_id, evaluation_mode...")
    op.add_column('task_evaluations', 
                  sa.Column('job_id', sa.Integer(), 
                           sa.ForeignKey('orchestration_jobs.id'), 
                           nullable=True))
    op.add_column('task_evaluations', 
                  sa.Column('evaluation_mode', sa.String(length=50), nullable=True))
    
    # 2. Convert feedback_for_generator from TEXT to JSONB
    print("Converting feedback_for_generator: TEXT -> JSONB...")
    op.execute("""
    ALTER TABLE task_evaluations 
    ALTER COLUMN feedback_for_generator TYPE JSONB 
    USING CASE 
      WHEN feedback_for_generator IS NULL THEN NULL
      WHEN TRIM(feedback_for_generator) LIKE '{%' OR TRIM(feedback_for_generator) LIKE '[%' 
        THEN feedback_for_generator::jsonb
      ELSE json_build_object('text', feedback_for_generator)::jsonb
    END;
    """)
    
    # 3. Convert metric_details from JSON to JSONB for consistency
    print("Converting metric_details: JSON -> JSONB...")
    op.execute("""
    ALTER TABLE task_evaluations 
    ALTER COLUMN metric_details TYPE JSONB 
    USING metric_details::jsonb;
    """)
    
    # 4. Backfill job_id from agent_tasks
    print("Backfilling job_id from agent_tasks...")
    op.execute("""
    UPDATE task_evaluations te
    SET job_id = at.job_id
    FROM agent_tasks at
    WHERE te.task_id = at.id
      AND te.job_id IS NULL;
    """)
    
    # 5. Backfill evaluation_mode for existing records
    print("Setting default evaluation_mode for existing records...")
    op.execute("""
    UPDATE task_evaluations
    SET evaluation_mode = CASE
      WHEN critic_type = 'fact_critic' THEN 'exam_comprehensive'
      WHEN critic_type = 'quality_critic' THEN 'exam_comprehensive'
      ELSE 'unknown'
    END
    WHERE evaluation_mode IS NULL;
    """)
    
    # 6. Drop redundant critic_type column
    print("Dropping redundant column: critic_type...")
    op.drop_column('task_evaluations', 'critic_type')
    
    # 7. Add indexes for query performance
    print("Creating indexes...")
    op.create_index('idx_task_evaluations_job_id', 'task_evaluations', ['job_id'])
    op.create_index('idx_task_evaluations_evaluation_mode', 'task_evaluations', ['evaluation_mode'])
    op.create_index('idx_task_evaluations_is_passed', 'task_evaluations', ['is_passed'])
    
    print("--- [Cook.ai] UPGRADE for 'improve_task_evaluations_schema' COMPLETED ---")


def downgrade() -> None:
    print("--- [Cook.ai] DOWNGRADE: Reverting TASK_EVALUATIONS schema changes ---")
    
    # 1. Drop indexes
    print("Dropping indexes...")
    op.drop_index('idx_task_evaluations_is_passed', table_name='task_evaluations')
    op.drop_index('idx_task_evaluations_evaluation_mode', table_name='task_evaluations')
    op.drop_index('idx_task_evaluations_job_id', table_name='task_evaluations')
    
    # 2. Restore critic_type column
    print("Restoring critic_type column...")
    op.add_column('task_evaluations', 
                  sa.Column('critic_type', sa.String(length=50), nullable=True))
    
    # Backfill critic_type from agent_tasks.agent_name
    op.execute("""
    UPDATE task_evaluations te
    SET critic_type = at.agent_name
    FROM agent_tasks at
    WHERE te.task_id = at.id;
    """)
    
    # 3. Revert metric_details from JSONB to JSON
    print("Reverting metric_details: JSONB -> JSON...")
    op.alter_column('task_evaluations', 'metric_details',
                   existing_type=postgresql.JSONB(astext_type=sa.Text()),
                   type_=sa.JSON(),
                   nullable=True)
    
    # 4. Revert feedback_for_generator from JSONB to TEXT
    print("Reverting feedback_for_generator: JSONB -> TEXT...")
    op.execute("""
    ALTER TABLE task_evaluations 
    ALTER COLUMN feedback_for_generator TYPE TEXT 
    USING CASE
      WHEN feedback_for_generator IS NULL THEN NULL
      WHEN feedback_for_generator ? 'text' THEN feedback_for_generator->>'text'
      ELSE feedback_for_generator::text
    END;
    """)
    
    # 5. Drop new columns
    print("Dropping columns: evaluation_mode, job_id...")
    op.drop_column('task_evaluations', 'evaluation_mode')
    op.drop_column('task_evaluations', 'job_id')
    
    print("--- [Cook.ai] DOWNGRADE for 'improve_task_evaluations_schema' COMPLETED ---")
