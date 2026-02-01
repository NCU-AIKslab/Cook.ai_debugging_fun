import os
import json
from sqlalchemy import (
    create_engine, MetaData, Table, Column, String, Integer, DateTime, Boolean,
    select, insert, update, and_, func, desc
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from dotenv import load_dotenv

from .OJ.models import ProblemConfig, TestCase, CaseResult, CaseStatus

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
metadata = MetaData()

# ==========================================
# 1. OJ 基礎 Tables
# ==========================================
problem_table = Table(
    "problem",
    metadata,
    Column("problem_id", String, primary_key=True),
    Column("test_cases", JSONB),
    Column("time_limit", Integer),
    Column("judge_type", String),
    Column("entry_point", String),
    schema="debugging",
    extend_existing=True,
)

submission_table = Table(
    "debugging_code_submission",
    metadata,
    Column("problem_id", String),
    Column("student_id", String),
    Column("result", JSONB),
    Column("code", JSONB),
    Column("output", JSONB),
    Column("submitted_at", DateTime, server_default=func.now()),
    schema="debugging",
    extend_existing=True,
)

# ==========================================
# 2. Pre-Coding Tables (觀念建構)
# ==========================================
precoding_question_table = Table(
    "precoding_question",
    metadata,
    Column("problem_id", String, primary_key=True),
    
    # 題目內容 (JSONB List)
    Column("logic_question", JSONB), 
    Column("error_code_question", JSONB),
    Column("explain_code_question", JSONB), # [New] 程式碼解釋題目
    
    Column("correct_code_template", JSONB),
    Column("created_at", DateTime, server_default=func.now()),
    schema="debugging",
    extend_existing=True,
)

precoding_student_answers_table = Table(
    "precoding_student_answers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("student_id", String, nullable=False),
    Column("problem_id", String, nullable=False),
    
    # 進度狀態: 'logic' -> 'error_code' -> 'explain_code' -> 'completed'
    Column("progress_stage", String, default="logic"), 
    
    # 學生作答紀錄 (JSONB List)
    Column("logic_responses", JSONB, default=[]),
    Column("error_responses", JSONB, default=[]),
    Column("explain_responses", JSONB, default=[]), # [New] 程式碼解釋作答紀錄

    Column("submitted_at", DateTime, server_default=func.now(), onupdate=func.now()),
    schema="debugging",
    extend_existing=True,
)

# ==========================================
# 2.5 Pre-Coding Logic Chatbot Tables (觀念建構 - 對話式)
# ==========================================

# 管理學生目前的階段與分數
precoding_logic_status_table = Table(
    "precoding_logic_status",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("student_id", String(50), nullable=False),
    Column("problem_id", String(50), nullable=False),
    Column("current_stage", String(20), default="UNDERSTANDING"),  # UNDERSTANDING, DECOMPOSITION, COMPLETED
    Column("current_score", Integer, default=1),  # 1-4 分
    Column("is_completed", Boolean, default=False),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
    schema="debugging",
    extend_existing=True,
)

# 對話紀錄表 (將整串對話塞進 chat_log JSONB 欄位)
precoding_logic_logs_table = Table(
    "precoding_logic_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("student_id", String(50), nullable=False),
    Column("problem_id", String(50), nullable=False),
    Column("chat_log", JSONB, default=[]),  # [{"role":..., "content":..., "stage":..., "score":..., "timestamp":...}]
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
    schema="debugging",
    extend_existing=True,
)

# ==========================================
# 3. CodingHelp Tables (AI 診斷與對話)
# ==========================================

# 1. 對話紀錄表
dialogue_table = Table(
    "debugging_dialogue",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("student_id", String, nullable=False),
    Column("problem_id", String, nullable=False),
    Column("num", Integer),            # 標記是第幾次 submit 的對話
    Column("student_question", JSONB), 
    Column("agent_reply", JSONB),      
    Column("zpd_level", Integer),      
    Column("submitted_at", DateTime, server_default=func.now()),
    schema="debugging",
    extend_existing=True,
)

# 2. 診斷報告表
evidence_report_table = Table(
    "debugging_evidence_report",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("student_id", String, nullable=False),
    Column("problem_id", String, nullable=False),
    Column("num", Integer),            # 標記是第幾次 submit 的診斷
    Column("evidence_report", JSONB),  
    Column("code", JSONB),            
    Column("submitted_at", DateTime, server_default=func.now()),
    schema="debugging",
    extend_existing=True,
)

# 3. 錯誤回顧練習表 (無 num)
practice_table = Table(
    "debugging_practice",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("student_id", String, nullable=False),
    Column("problem_id", String, nullable=False),
    Column("code_question", JSONB),       
    Column("code_correct_answer", JSONB), 
    Column("student_answer", JSONB),      
    Column("answer_is_correct", Boolean), # 整體是否通過
    Column("submitted_at", DateTime, server_default=func.now()),
    schema="debugging",
    extend_existing=True,
)

# ==========================================
# Helper Functions
# ==========================================

def load_problem_config(problem_id: str) -> ProblemConfig:
    with engine.connect() as conn:
        row = conn.execute(
            select(
                problem_table.c.problem_id,
                problem_table.c.test_cases,
                problem_table.c.time_limit,
                problem_table.c.judge_type,
                problem_table.c.entry_point,
            ).where(problem_table.c.problem_id == problem_id)
        ).fetchone()

    if not row:
        raise ValueError("Problem not found")

    row_mapping = row._mapping if hasattr(row, "_mapping") else row
    tc_list = row_mapping["test_cases"] or []
    test_cases = [TestCase(tc["input"], tc["output"]) for tc in tc_list]

    return ProblemConfig(
        problem_id=row_mapping["problem_id"],
        judge_type=row_mapping["judge_type"] or "stdio",
        entry_point=row_mapping["entry_point"],
        time_limit_ms=row_mapping["time_limit"] or 1000,
        test_cases=test_cases,
    )

def save_submission(problem_id, student_id, code, verdict, results):
    summary = {
        "verdict": verdict,
        "passed_cases": f"{len([r for r in results if r.status == CaseStatus.AC])}/{len(results)}",
        "details": [vars(r) for r in results],
    }
    
    with engine.connect() as conn:
        conn.execute(
            insert(submission_table).values(
                problem_id=problem_id,
                student_id=student_id,
                result=json.dumps(verdict),
                code={"content": code},
                output=summary,
            )
        )
        conn.commit()

def get_latest_submission(student_id: str, problem_id: str):
    stmt = select(
        submission_table.c.code,
        submission_table.c.result,
        submission_table.c.output,
        submission_table.c.submitted_at
    ).where(
        submission_table.c.student_id == student_id,
        submission_table.c.problem_id == problem_id
    ).order_by(
        submission_table.c.submitted_at.desc()
    ).limit(1)

    with engine.connect() as conn:
        row = conn.execute(stmt).fetchone()

    if row:
        row_mapping = row._mapping if hasattr(row, "_mapping") else row
        return {
            "code": row_mapping["code"],           
            "result": row_mapping["result"],       
            "output": row_mapping["output"],       
            "submitted_at": row_mapping["submitted_at"]
        }
    return None

def get_submission_count(student_id: str, problem_id: str) -> int:
    with engine.connect() as conn:
        query = select(func.count()).select_from(submission_table).where(
            submission_table.c.student_id == student_id,
            submission_table.c.problem_id == problem_id
        )
        count = conn.execute(query).scalar()
        return count if count else 0

def get_practice_status(student_id: str, problem_id: str):
    """
    回傳: {"exists": bool, "completed": bool, "data": List[Question], "student_answer": List, "id": int}
    """
    stmt = select(
        practice_table.c.id,
        practice_table.c.code_question,
        practice_table.c.answer_is_correct,
        practice_table.c.student_answer # 新增回傳學生歷史作答
    ).where(
        practice_table.c.student_id == student_id,
        practice_table.c.problem_id == problem_id
    ).order_by(desc(practice_table.c.submitted_at)).limit(1)

    with engine.connect() as conn:
        row = conn.execute(stmt).fetchone()
        
    if row:
        mapping = row._mapping if hasattr(row, "_mapping") else row
        return {
            "exists": True,
            "completed": mapping["answer_is_correct"] if mapping["answer_is_correct"] is not None else False,
            "data": mapping["code_question"],
            "student_answer": mapping["student_answer"],
            "id": mapping["id"]
        }
    return {"exists": False, "completed": False, "data": None, "id": None}

def update_practice_answer(practice_id: int, student_answers: list, is_all_correct: bool):
    """
    更新練習題作答結果 (List)
    """
    stmt = update(practice_table).where(
        practice_table.c.id == practice_id
    ).values(
        student_answer=student_answers,
        answer_is_correct=is_all_correct
    )
    with engine.begin() as conn:
        conn.execute(stmt)