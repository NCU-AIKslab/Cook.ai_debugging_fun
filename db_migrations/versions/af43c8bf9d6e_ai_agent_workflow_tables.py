"""ai_agent_workflow_tables

Revision ID: af43c8bf9d6e
Revises: 9678c41f4f97
Create Date: 2025-11-08 15:22:55.888351

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'af43c8bf9d6e'
down_revision: Union[str, None] = '9678c41f4f97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Phase 1-C: AI Agent 生成流程 ###
    
    # --- 解決循環依賴 (Circular Dependency) ---
    # 我們的 JOBS -> CONTENTS -> TASKS -> JOBS 之間有循環依賴
    # 策略：
    # 1. 建立 JOBS (不含 FK)
    # 2. 建立 TASKS (含 FK -> JOBS)
    # 3. 建立 CONTENTS (含 FK -> TASKS)
    # 4. 最後才用 ALTER TABLE 補上 JOBS 的 FK (-> CONTENTS)
    
    # 1. 建立 ORCHESTRATION_JOBS (任務總表)
    op.execute("""
    CREATE TABLE ORCHESTRATION_JOBS (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        input_prompt TEXT,
        status VARCHAR(50) NOT NULL DEFAULT 'planning',
        
        -- 暫時不加 FK，欄位允許 NULL
        final_output_id INTEGER, 
        
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        
        -- 實驗設定
        workflow_type VARCHAR(50),
        experiment_config JSON,
        
        -- 實驗數據 logs
        total_iterations INTEGER,
        total_latency_ms INTEGER,
        total_prompt_tokens INTEGER,
        total_completion_tokens INTEGER,
        estimated_carbon_g DECIMAL,
        
        CONSTRAINT fk_jobs_user
            FOREIGN KEY(user_id) 
            REFERENCES USERS(id)
            ON DELETE SET NULL
    );
    """)

    # 2. 建立 AGENT_TASKS (Agent 子任務)
    op.execute("""
    CREATE TABLE AGENT_TASKS (
        id SERIAL PRIMARY KEY,
        job_id INTEGER NOT NULL,
        parent_task_id INTEGER,
        iteration_number INTEGER DEFAULT 1,
        
        -- 執行任務內容
        agent_name VARCHAR(100),
        task_description TEXT,
        task_input JSON,
        output TEXT,
        status VARCHAR(50) NOT NULL DEFAULT 'pending',
        error_message TEXT,
        
        -- 效能與成本追蹤
        duration_ms INTEGER,
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        estimated_cost_usd DECIMAL,
        
        -- 模型版本控制
        model_name VARCHAR(100),
        model_parameters JSON,
        
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMPTZ,
        
        CONSTRAINT fk_tasks_job
            FOREIGN KEY(job_id) 
            REFERENCES ORCHESTRATION_JOBS(id)
            ON DELETE CASCADE,
            
        CONSTRAINT fk_tasks_parent
            FOREIGN KEY(parent_task_id) 
            REFERENCES AGENT_TASKS(id)
            ON DELETE SET NULL
    );
    """)

    # 3. 建立 GENERATED_CONTENTS (AI 生成的內容)
    op.execute("""
    CREATE TABLE GENERATED_CONTENTS (
        id SERIAL PRIMARY KEY,
        source_agent_task_id INTEGER, -- 是哪個 Task 產生的
        content_type VARCHAR(50) NOT NULL,
        content JSON NOT NULL,
        teacher_rating INTEGER, -- 1-5 星
        title VARCHAR(255) NOT NULL,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        
        CONSTRAINT fk_contents_task
            FOREIGN KEY(source_agent_task_id) 
            REFERENCES AGENT_TASKS(id)
            ON DELETE SET NULL
    );
    """)

    # 4. FK: ORCHESTRATION_JOBS -> GENERATED_CONTENTS
    op.execute("""
    ALTER TABLE ORCHESTRATION_JOBS
    ADD CONSTRAINT fk_jobs_final_output
        FOREIGN KEY(final_output_id) 
        REFERENCES GENERATED_CONTENTS(id)
        ON DELETE SET NULL;
    """)

    # 5. 建立 TASK_EVALUATIONS (自評機制)
    op.execute("""
    CREATE TABLE TASK_EVALUATIONS (
        id SERIAL PRIMARY KEY,
        task_id INTEGER NOT NULL,
        evaluation_stage INTEGER,
        critic_type VARCHAR(50),
        is_passed BOOLEAN,
        feedback_for_generator TEXT,
        metric_details JSON,
        evaluated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        
        CONSTRAINT fk_evaluations_task
            FOREIGN KEY(task_id) 
            REFERENCES AGENT_TASKS(id)
            ON DELETE CASCADE
    );
    """)

    # 6. 建立 CONTENT_EDIT_HISTORY (教師編輯紀錄)
    op.execute("""
    CREATE TABLE CONTENT_EDIT_HISTORY (
        id SERIAL PRIMARY KEY,
        generated_content_id INTEGER NOT NULL,
        user_id INTEGER,
        diff_content JSON,
        edited_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        
        CONSTRAINT fk_history_content
            FOREIGN KEY(generated_content_id) 
            REFERENCES GENERATED_CONTENTS(id)
            ON DELETE CASCADE,
            
        CONSTRAINT fk_history_user
            FOREIGN KEY(user_id) 
            REFERENCES USERS(id)
            ON DELETE SET NULL
    );
    """)

    # 7. 建立 ORCHESTRATION_JOB_SOURCES (任務 RAG 來源)
    op.execute("""
    CREATE TABLE ORCHESTRATION_JOB_SOURCES (
        job_id INTEGER NOT NULL,
        source_type VARCHAR(20) NOT NULL, -- 'content' or 'chunk'
        source_id INTEGER NOT NULL,      -- unique_content_id or document_chunk_id
        
        PRIMARY KEY (job_id, source_type, source_id),
        
        CONSTRAINT fk_job_sources_job
            FOREIGN KEY(job_id) 
            REFERENCES ORCHESTRATION_JOBS(id)
            ON DELETE CASCADE
        -- 注意：source_id 我們不建立 FK，因為它是多態的 (Polymorphic)
    );
    """)

    # 8. 建立 AGENT_TASK_SOURCES (子任務 RAG 來源)
    op.execute("""
    CREATE TABLE AGENT_TASK_SOURCES (
        task_id INTEGER NOT NULL,
        source_type VARCHAR(20) NOT NULL, -- 'content' or 'chunk'
        source_id INTEGER NOT NULL,      -- unique_content_id or document_chunk_id
        
        PRIMARY KEY (task_id, source_type, source_id),
        
        CONSTRAINT fk_task_sources_task
            FOREIGN KEY(task_id) 
            REFERENCES AGENT_TASKS(id)
            ON DELETE CASCADE
    );
    """)
    
    print("--- [Cook.ai] UPGRADE for 'ai_agent_workflow_tables' COMPLETED ---")


def downgrade() -> None:
    
    print("--- [Cook.ai] EXECUTING DOWNGRADE for 'ai_agent_workflow_tables' ---")

    op.execute("DROP TABLE IF EXISTS AGENT_TASK_SOURCES;")
    op.execute("DROP TABLE IF EXISTS ORCHESTRATION_JOB_SOURCES;")
    op.execute("DROP TABLE IF EXISTS CONTENT_EDIT_HISTORY;")
    op.execute("DROP TABLE IF EXISTS TASK_EVALUATIONS;")
    
    # 刪除 FK，才能刪除依賴的表
    op.execute("ALTER TABLE ORCHESTRATION_JOBS DROP CONSTRAINT IF EXISTS fk_jobs_final_output;")
    
    op.execute("DROP TABLE IF EXISTS GENERATED_CONTENTS;")
    op.execute("DROP TABLE IF EXISTS AGENT_TASKS;")
    op.execute("DROP TABLE IF EXISTS ORCHESTRATION_JOBS;")
    
    print("--- [Cook.ai] DOWNGRADE for 'ai_agent_workflow_tables' COMPLETED ---")