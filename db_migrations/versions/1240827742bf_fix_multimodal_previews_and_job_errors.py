"""fix_multimodal_previews_and_job_errors

Revision ID: 1240827742bf
Revises: b649d64cbd8b
Create Date: 2025-11-08 18:53:11.675919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1240827742bf'
down_revision: Union[str, Sequence[str], None] = 'b649d64cbd8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### 結構修正 (Schema Fixes - Multimodal) ###

    print("--- Renaming 'material_previews' to 'document_content' ---")
    op.rename_table('material_previews', 'document_content')
    
    print("--- [Cook.ai] Applying Schema Fixes (Multimodal) ---")
    
    # 1. 刪除舊的、不符需求的欄位
    print("--- Dropping old columns from 'material_previews' ---")
    op.drop_column('document_content', 'extracted_text')
    op.drop_column('document_content', 'preview_image_path')
    op.drop_column('document_content', 'ocr_text')
    
    # 2. 新增 "人類可讀" 且 "RAG-ready" 的純文字欄位
    print("--- Adding 'combined_human_text' to 'document_content' ---")
    op.add_column('document_content', 
                  sa.Column('combined_human_text', sa.Text(), nullable=True))
                  
    # 3. 新增 "結構化" 欄位，用於儲存 [text, image(base64, ocr)] 序列
    print("--- Adding 'structured_content' (JSON) to 'document_content' ---")
    op.add_column('document_content', 
                  sa.Column('structured_content', sa.JSON(), nullable=True))

    print("--- [Cook.ai] Schema Fixes (Multimodal) Applied Successfully ---")


def downgrade() -> None:
    # ### 這裡是「反悔」時要執行的，順序必須和 upgrade() 相反 ###
    
    print("--- [Cook.ai] Reverting Schema Fixes (Multimodal) ---")

    # 2. 還原 MATERIAL_PREVIEWS 表 (回到 1-B 的原始狀態)
    op.drop_column('document_content', 'structured_content')
    op.drop_column('document_content', 'combined_human_text')
    
    op.add_column('document_content', 
                  sa.Column('ocr_text', sa.Text(), nullable=True))
    op.add_column('document_content', 
                  sa.Column('preview_image_path', sa.VARCHAR(length=512), nullable=True))
    op.add_column('document_content', 
                  sa.Column('extracted_text', sa.Text(), nullable=True))
    
    print("--- Renaming 'document_content' back to 'material_previews' ---")
    op.rename_table('document_content', 'material_previews')

    print("--- [Cook.ai] Schema Fixes (Multimodal) Reverted ---")