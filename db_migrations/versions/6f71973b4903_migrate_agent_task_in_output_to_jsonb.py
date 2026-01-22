"""migrate agent_task in, output to jsonb

Revision ID: 6f71973b4903
Revises: acfe2cfc333b
Create Date: 2025-11-16 17:01:39.077682

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6f71973b4903'
down_revision: Union[str, Sequence[str], None] = 'acfe2cfc333b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print("--- [Cook.ai] UPGRADE: Migrating AGENT_TASKS in&output columns to JSONB ---")

    # 建立一個暫時的 "安全轉換" 輔助函數
    print("Creating temporary function public.safe_cast_to_jsonb()...")
    op.execute("""
    CREATE OR REPLACE FUNCTION public.safe_cast_to_jsonb(text_data TEXT)
    RETURNS JSONB AS $$
    BEGIN
        -- 步驟 A: 嘗試將單引號替換成雙引號，然後轉換
        RETURN REPLACE(text_data, '''', '"')::jsonb;
    EXCEPTION
        -- 步驟 B: 如果轉換失敗 (例如 "invalid input syntax" 錯誤)
        WHEN invalid_text_representation THEN
            -- 將整筆原始的「髒資料」包裝成一個 {"message": "..."} 物件
            RETURN jsonb_build_object('corrupted_message', text_data);
    END;
    $$ LANGUAGE plpgsql;
    """)

    # 移 AGENT_TASKS.task_input 欄位 (JSON -> JSONB)
    print("Migrating column: AGENT_TASKS.task_input (JSON -> JSONB) with safety net...")
    op.execute("""
    ALTER TABLE AGENT_TASKS
    ALTER COLUMN task_input
    TYPE JSONB
    USING (
        public.safe_cast_to_jsonb(task_input::text) -- 先轉成 text 再傳入
    );
    """)

    # 遷移 AGENT_TASKS.output 欄位 (TEXT -> JSONB)
    print("Migrating column: AGENT_TASKS.output (TEXT -> JSONB) with safety net...")
    op.execute("""
    ALTER TABLE AGENT_TASKS
    ALTER COLUMN output
    TYPE JSONB
    USING (
      CASE
        WHEN output IS NULL THEN NULL
        
        -- 情況 B: 如果是 JSON-like 字串 (用 { 或 [ 開頭)
        WHEN TRIM(output) LIKE '{%' OR TRIM(output) LIKE '[%' THEN
          public.safe_cast_to_jsonb(output) -- 使用安全函數
          
        -- 情況 C: 其他所有情況 (例如 "Retrieved 3 chunks.")
        ELSE
          jsonb_build_object('message', output)
      END
    );
    """)
    
    # 遷移 GENERATED_CONTENTS.content 欄位 (JSON -> JSONB)
    print("Migrating column: GENERATED_CONTENTS.content (JSON -> JSONB) with safety net...")
    op.execute("""
    ALTER TABLE GENERATED_CONTENTS
    ALTER COLUMN content
    TYPE JSONB
    USING (
        -- 【修正】使用統一的函數名稱
        public.safe_cast_to_jsonb(content::text)
    );
    """)
    
    # 刪除暫時的輔助函數
    print("Dropping temporary function public.safe_cast_to_jsonb()...")
    op.execute("DROP FUNCTION public.safe_cast_to_jsonb(TEXT);")

    print("--- [Cook.ai] UPGRADE for 'migrate_agent_tasks_to_jsonb' COMPLETED ---")


def downgrade() -> None:
    print("--- [Cook.ai] DOWNGRADE: Reverting AGENT_TASKS columns to original types ---")
    
    # 將 'output' 欄位從 JSONB 還原回 TEXT (原始型別是 TEXT)
    op.alter_column('AGENT_TASKS', 'output',
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
            type_=sa.TEXT(),
            nullable=True)
            
    # 將 'task_input' 欄位從 JSONB 還原回 JSON (原始型別是 JSON)
    op.alter_column('AGENT_TASKS', 'task_input',
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
            type_=sa.JSON(),
            nullable=True)

    # 將 'GENERATED_CONTENTS.content' 欄位從 JSONB 還原回 JSON
    op.alter_column('GENERATED_CONTENTS', 'content',
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
            type_=sa.JSON(),
            nullable=False)

    # 4. 清理在 upgrade 時建立的暫存輔助函數
    print("Dropping temporary function public.safe_cast_to_jsonb() if it exists...")
    op.execute("DROP FUNCTION IF EXISTS public.safe_cast_to_jsonb(TEXT);")

    print("--- [Cook.ai] DOWNGRADE for 'migrate_agent_tasks_to_jsonb' COMPLETED ---")