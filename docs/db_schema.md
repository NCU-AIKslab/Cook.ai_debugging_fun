erDiagram
    %% --- 1. 使用者與角色 ---
    ROLES {
        INTEGER id PK
        VARCHAR(50) name UK "角色名稱: 如teacher, student, TA"
    }
    
    USERS {
        INTEGER id PK 
        VARCHAR(255) email UK "登入Email"
        VARCHAR(100) full_name "使用者名稱"
        INTEGER role_id FK "使用者角色 (FK -> ROLES.id)"
        DATETIME created_time 
        DATETIME last_login_time
    }
    
    USER_AUTHENTICATIONS {
        INTEGER id PK
        INTEGER user_id FK "使用者 (FK -> USERS.id)"
        VARCHAR(50) provider "驗證提供者: 如local, google"
        VARCHAR(255) password "加密後的使用者密碼"
    }
    STUDENT_PROFILES {
        INTEGER user_id PK, FK "-> USERS.id (一對一主鍵)"
        VARCHAR(100) student_id UK "學號 (e.g., '109xxxxxx')"
        VARCHAR(100) major "科系 (可選)"
        INTEGER enrollment_year "入學年份 (已移除)"
    }

    %% --- 2. 課程與選課 ---
    
    COURSES {
        INTEGER id PK
        INTEGER teacher_id FK "授課教師(FK -> USERS.id)"
        VARCHAR(100) semester_name "學期名稱，如: 1141"
        VARCHAR(255) name "課程名稱，如: 創意學習"
        TEXT description "課程簡介"
        DATETIME created_at "課程建立時間"
    }
    
    ENROLLMENTS {
        INTEGER user_id PK, FK "學生ID (PK, FK -> USERS.id)"
        INTEGER course_id PK, FK "課程ID (PK, FK -> COURSES.id)"
        DATETIME enrolled_at "選課時間"
    }

    %% --- 3. 資源池層 (Resource Pool) - 實體內容 ---
    
    UNIQUE_CONTENTS {
        INTEGER id PK
        VARCHAR(64) content_hash UK "SHA-256 hash of the file content"
        INTEGER file_size_bytes
        VARCHAR(20) original_file_type "e.g., 'pdf', 'docx'"
        VARCHAR(20) processing_status "'pending', 'completed', 'failed'"
        DATETIME created_at "上傳時間"
    }
    
    %% 原 MATERIALS 表 (改名)
    UPLOADED_CONTENTS {
        INTEGER id PK
        INTEGER course_id FK "FK -> COURSES.id"
        INTEGER uploader_id FK "上傳者 (FK -> USERS.id)"
        VARCHAR(255) file_name "原始檔名"
        INTEGER unique_content_id FK "FK -> UNIQUE_CONTENTS.id"
        DATETIME created_at
        DATETIME updated_at
    }
    
    GENERATED_CONTENTS {
        INTEGER id PK
        INTEGER source_agent_task_id FK "-> AGENT_TASKS.id"
        VARCHAR(50) content_type NOT NULL "e.g., 'multiple_choice', 'summary'"
        JSON content NOT NULL "儲存生成結果之結構化內容(json)"
        INTEGER teacher_rating "教師對於此次生成結果的回饋"
        VARCHAR(255) title NOT NULL "標題"
        DATETIME created_at
        DATETIME updated_at
    }
    
    %% --- 4. 應用層 (Application Layer) - 章節與內容 ---
    
    COURSE_UNITS {
        INTEGER id PK
        INTEGER course_id FK "-> COURSES.id"
        INTEGER topic_id "章節編號 (1, 2, 3...)"
        VARCHAR(255) name "單元名稱 (e.g., 第三章 光合作用)"
        TEXT description "章節說明 (Markdown)"
        DATETIME updated_at
    }
    
    COURSE_MATERIALS {
        INTEGER id PK
        INTEGER course_id FK
        INTEGER course_unit_id FK "-> COURSE_UNITS.id"
        VARCHAR(255) title "教材標題"
        TEXT description "教材說明"
        BOOLEAN is_visible "是否顯示"
        INTEGER display_order "排序"
        
        %% 多態關聯
        VARCHAR(50) source_type "'uploaded_content', 'generated_content'"
        INTEGER source_id "對應 UPLOADED_CONTENTS.id 或 GENERATED_CONTENTS.id"
        
        DATETIME created_at
        DATETIME updated_at
    }

    COURSE_ASSIGNMENTS {
        INTEGER id PK
        INTEGER course_id FK
        INTEGER course_unit_id FK "-> COURSE_UNITS.id"
        INTEGER author_id FK "-> USERS.id"
        VARCHAR(255) title "作業標題"
        VARCHAR(50) assignment_timing "'pre_class', 'post_class'"
        DATETIME due_date "截止日期"
        
        %% 多態關聯
        VARCHAR(50) source_type "'uploaded_content', 'generated_content'"
        INTEGER source_id "對應 UPLOADED_CONTENTS.id 或 GENERATED_CONTENTS.id"
        
        DATETIME created_at
        DATETIME updated_at
    }
    
    COURSE_ANNOUNCEMENTS {
        INTEGER id PK
        INTEGER course_id FK "-> COURSES.id"
        INTEGER author_id FK "-> USERS.id"
        VARCHAR(255) title "公告標題"
        TEXT content "公告內容"
        BOOLEAN is_pinned "是否置頂"
        DATETIME created_at
        DATETIME updated_at
    }

    %% --- 5. 學生互動 (繳交與評分) ---

    SUBMISSIONS {
        INTEGER id PK
        INTEGER assignment_id FK "-> COURSE_ASSIGNMENTS.id"
        INTEGER user_id FK "-> USERS.id (繳交學生)"
        JSON content "學生提交的答案"
        DECIMAL grade "分數"
        TEXT feedback "教師評語"
        DATETIME submitted_at "繳交時間"
        DATETIME updated_at
    }
    
    SUBMISSION_ATTACHMENTS {
        INTEGER id PK
        INTEGER submission_id FK "-> SUBMISSIONS.id"
        VARCHAR(255) file_name
        VARCHAR(512) file_path
        DATETIME created_at
    }

    %% --- 6. RAG 與 文檔處理 ---

    DOCUMENT_CONTENT {
        INTEGER id PK
        INTEGER unique_content_id FK "FK -> UNIQUE_CONTENTS.id"
        INTEGER page_number
        JSON structured_content
        TEXT combined_human_text
    }
    
    DOCUMENT_CHUNKS {
        INTEGER id PK
        INTEGER unique_content_id FK "FK -> UNIQUE_CONTENTS.id"
        TEXT chunk_text
        INTEGER chunk_order
        JSON metadata
        VECTOR(1536) embedding
    }

    %% --- 7. AI Agent 流程與評估 ---
    
    ORCHESTRATION_JOBS {
        INTEGER id PK
        INTEGER user_id FK
        TEXT input_prompt
        VARCHAR(50) status
        TEXT error_message
        INTEGER final_output_id FK
        DATETIME created_at
        DATETIME updated_at
        VARCHAR(50) workflow_type
        JSON experiment_config
        INTEGER total_iterations
        INTEGER total_latency_ms
        INTEGER total_prompt_tokens
        INTEGER total_completion_tokens
        DECIMAL estimated_carbon_g
    }
    
    ORCHESTRATION_JOB_SOURCES {
        INTEGER job_id PK, FK
        VARCHAR(20) source_type PK
        INTEGER source_id PK
    }
    
    AGENT_TASKS {
        INTEGER id PK
        INTEGER job_id FK
        INTEGER parent_task_id FK
        INTEGER iteration_number
        VARCHAR(100) agent_name
        TEXT task_description
        JSON task_input
        TEXT output
        VARCHAR(50) status
        TEXT error_message
        INTEGER duration_ms
        INTEGER prompt_tokens
        INTEGER completion_tokens
        DECIMAL estimated_cost_usd
        VARCHAR(100) model_name
        JSON model_parameters
        DATETIME created_at
        DATETIME completed_at
    }
    
    AGENT_TASK_SOURCES {
        INTEGER task_id PK, FK
        VARCHAR(20) source_type PK
        INTEGER source_id PK
    }
    
    TASK_EVALUATIONS {
        INTEGER id PK
        INTEGER task_id FK
        INTEGER job_id FK
        INTEGER evaluation_stage
        VARCHAR(50) evaluation_mode
        BOOLEAN is_passed
        JSONB feedback_for_generator
        JSONB metric_details
        DATETIME evaluated_at
    }
    
    CONTENT_EDIT_HISTORY {
        INTEGER id PK
        INTEGER generated_content_id FK
        INTEGER user_id FK
        JSON diff_content
        DATETIME edited_at
    }
    
    KNOWLEDGE_POINTS {
        INTEGER id PK
        INTEGER unit_id FK "-> COURSE_UNITS.id"
        INTEGER course_id FK "-> COURSES.id"
        VARCHAR(255) name
        INTEGER display_order
    }

    MATERIAL_KNOWLEDGE_POINTS {
        INTEGER material_id PK "注意：這裡目前可能需要調整為對應 UPLOADED_CONTENTS.id"
        INTEGER knowledge_point_id PK
    }
    
    QUESTIONS {
        INTEGER id PK
        INTEGER course_id FK
        INTEGER creator_id FK
        INTEGER kp_id FK
        JSON content
    }