"""add multimodal_metadata to document_chunks

Revision ID: db7352f76a08
Revises: 76f60c43958b
Create Date: 2025-12-17 15:05:43.476973

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db7352f76a08'
down_revision: Union[str, Sequence[str], None] = '76f60c43958b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add multimodal_metadata column to document_chunks table for Phase 1+3 RAG optimization."""
    print("--- [Cook.ai] UPGRADE: Adding multimodal_metadata to document_chunks ---")
    
    # Import  postgresql for JSONB type
    from sqlalchemy.dialects import postgresql
    
    # 1. Add multimodal_metadata column
    print("Adding column: multimodal_metadata (JSONB)...")
    op.add_column('document_chunks', 
                  sa.Column('multimodal_metadata', 
                           postgresql.JSONB(astext_type=sa.Text()),
                           nullable=True))
    
    # 2. Add GIN index for faster JSONB querying
    print("Creating GIN index: idx_chunks_multimodal...")
    op.create_index('idx_chunks_multimodal', 
                   'document_chunks', 
                   ['multimodal_metadata'], 
                   postgresql_using='gin')
    
    print("--- [Cook.ai] UPGRADE for 'add_multimodal_metadata' COMPLETED ---")
    print("")
    print("ℹ️  Column structure:")
    print("   {")
    print("     'images': [{'position': int, 'base64': str, 'ocr_text': str}],")
    print("     'text_only': str,")
    print("     'contains_code': bool")
    print("   }")


def downgrade() -> None:
    """Remove multimodal_metadata column from document_chunks table."""
    print("--- [Cook.ai] DOWNGRADE: Removing multimodal_metadata from document_chunks ---")
    
    # 1. Drop index
    print("Dropping index: idx_chunks_multimodal...")
    op.drop_index('idx_chunks_multimodal', table_name='document_chunks')
    
    # 2. Drop column
    print("Dropping column: multimodal_metadata...")
    op.drop_column('document_chunks', 'multimodal_metadata')
    
    print("--- [Cook.ai] DOWNGRADE for 'add_multimodal_metadata' COMPLETED ---")

