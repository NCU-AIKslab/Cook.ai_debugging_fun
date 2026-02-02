-- Pre-Coding Logic Chatbot Tables Migration
-- Run this SQL to create the necessary tables for the new Pre-Coding chatbot feature

-- 建立目前狀態表 (管理學生目前的階段與分數)
CREATE TABLE IF NOT EXISTS debugging.precoding_logic_status (
    id SERIAL PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    problem_id VARCHAR(50) NOT NULL,
    current_stage VARCHAR(20) DEFAULT 'UNDERSTANDING', -- UNDERSTANDING, DECOMPOSITION, COMPLETED
    current_score INTEGER DEFAULT 1,                  -- 1-4 分
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, problem_id) -- 同一個學生同題目只有一個 Session
);

-- 建立對話紀錄表 (將整串對話塞進 chat_log JSONB 欄位)
CREATE TABLE IF NOT EXISTS debugging.precoding_logic_logs (
    id SERIAL PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    problem_id VARCHAR(50) NOT NULL,
    chat_log JSONB DEFAULT '[]'::jsonb, -- 格式: [{"role":..., "content":..., "stage":..., "score":..., "timestamp":...}]
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, problem_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_precoding_logic_status_student_problem 
    ON debugging.precoding_logic_status(student_id, problem_id);

CREATE INDEX IF NOT EXISTS idx_precoding_logic_logs_student_problem 
    ON debugging.precoding_logic_logs(student_id, problem_id);
