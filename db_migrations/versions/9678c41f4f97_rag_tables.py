"""rag_tables

Revision ID: 9678c41f4f97
Revises: 38cd27565f73
Create Date: 2025-11-07 20:58:52.745965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9678c41f4f97'
down_revision: Union[str, None] = '38cd27565f73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 啟用 pgvector 擴充以支援向量欄位
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. 建立 COURSE_UNITS 表
    op.execute("""
    CREATE TABLE COURSE_UNITS (
        id SERIAL PRIMARY KEY,
        course_id INTEGER NOT NULL,
        chapter_name VARCHAR(255) NOT NULL,
        week INTEGER,
        display_order INTEGER,
        
        CONSTRAINT fk_units_course
            FOREIGN KEY(course_id) 
            REFERENCES COURSES(id)
            ON DELETE CASCADE
    );
    """)
    
    # 3. 建立 UNIQUE_CONTENTS 表
    op.execute("""
    CREATE TABLE UNIQUE_CONTENTS (
        id SERIAL PRIMARY KEY,
        content_hash VARCHAR(64) UNIQUE NOT NULL,
        file_size_bytes INTEGER,
        original_file_type VARCHAR(20),
        processing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. 建立 MATERIALS 表
    op.execute("""
    CREATE TABLE MATERIALS (
        id SERIAL PRIMARY KEY,
        course_id INTEGER NOT NULL,
        uploader_id INTEGER NOT NULL,
        course_unit_id INTEGER,
        file_name VARCHAR(255) NOT NULL,
        unique_content_id INTEGER NOT NULL,
        
        CONSTRAINT fk_materials_course
            FOREIGN KEY(course_id) 
            REFERENCES COURSES(id)
            ON DELETE CASCADE,
            
        CONSTRAINT fk_materials_uploader
            FOREIGN KEY(uploader_id) 
            REFERENCES USERS(id)
            ON DELETE SET NULL,
                
        CONSTRAINT fk_materials_unit
            FOREIGN KEY(course_unit_id) 
            REFERENCES COURSE_UNITS(id)
            ON DELETE SET NULL,
            
        CONSTRAINT fk_materials_unique_content
            FOREIGN KEY(unique_content_id) 
            REFERENCES UNIQUE_CONTENTS(id)
            ON DELETE CASCADE
    );
    """)

    # 5. 建立 MATERIAL_PREVIEWS 表
    op.execute("""
    CREATE TABLE MATERIAL_PREVIEWS (
        id SERIAL PRIMARY KEY,
        unique_content_id INTEGER NOT NULL,
        page_number INTEGER,
        extracted_text TEXT,
        ocr_text TEXT,
        preview_image_path VARCHAR(512),
        
        CONSTRAINT fk_previews_unique_content
            FOREIGN KEY(unique_content_id) 
            REFERENCES UNIQUE_CONTENTS(id)
            ON DELETE CASCADE
    );
    """)

    # 6. 建立 DOCUMENT_CHUNKS 表 (For RAG)
    op.execute("""
    CREATE TABLE DOCUMENT_CHUNKS (
        id SERIAL PRIMARY KEY,
        unique_content_id INTEGER NOT NULL,
        chunk_text TEXT,
        chunk_order INTEGER,
        metadata JSON,
        embedding VECTOR(1536), -- 需要 pgvector 擴充
        
        CONSTRAINT fk_chunks_unique_content
            FOREIGN KEY(unique_content_id) 
            REFERENCES UNIQUE_CONTENTS(id)
            ON DELETE CASCADE
    );
    """)

    # 7. 建立向量索引 (HNSW) 以加速搜尋
    op.execute("""
    CREATE INDEX IF NOT EXISTS hnsw_idx_document_chunks_embedding
    ON DOCUMENT_CHUNKS
    USING HNSW (embedding vector_cosine_ops);
    """)

    # 8. 建立 KNOWLEDGE_POINTS 表
    op.execute("""
    CREATE TABLE KNOWLEDGE_POINTS (
        id SERIAL PRIMARY KEY,
        unit_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        name VARCHAR(255) NOT NULL,
        display_order INTEGER,
        
        CONSTRAINT fk_kp_unit
            FOREIGN KEY(unit_id) 
            REFERENCES COURSE_UNITS(id)
            ON DELETE CASCADE,
            
        CONSTRAINT fk_kp_course
            FOREIGN KEY(course_id) 
            REFERENCES COURSES(id)
            ON DELETE NO ACTION -- 避免和 unit 造成多重 CASCADE
    );
    """)

    # 9. 建立 MATERIAL_KNOWLEDGE_POINTS 多對多關聯表
    op.execute("""
    CREATE TABLE MATERIAL_KNOWLEDGE_POINTS (
        material_id INTEGER NOT NULL,
        knowledge_point_id INTEGER NOT NULL,
        
        PRIMARY KEY (material_id, knowledge_point_id),
        
        CONSTRAINT fk_mkp_material
            FOREIGN KEY(material_id) 
            REFERENCES MATERIALS(id)
            ON DELETE CASCADE,
            
        CONSTRAINT fk_mkp_knowledge_point
            FOREIGN KEY(knowledge_point_id) 
            REFERENCES KNOWLEDGE_POINTS(id)
            ON DELETE CASCADE
    );
    """)



def downgrade() -> None:
    
    op.execute("DROP INDEX IF EXISTS hnsw_idx_document_chunks_embedding;")
    
    op.execute("DROP TABLE IF EXISTS MATERIAL_KNOWLEDGE_POINTS;")
    op.execute("DROP TABLE IF EXISTS KNOWLEDGE_POINTS;")
    op.execute("DROP TABLE IF EXISTS DOCUMENT_CHUNKS;")
    op.execute("DROP TABLE IF EXISTS MATERIAL_PREVIEWS;")
    op.execute("DROP TABLE IF EXISTS MATERIALS;")
    op.execute("DROP TABLE IF EXISTS COURSE_UNITS;")
    op.execute("DROP TABLE IF EXISTS UNIQUE_CONTENTS;")
    
    # op.execute("DROP EXTENSION IF EXISTS vector;")
