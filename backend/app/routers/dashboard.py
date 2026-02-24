# -*- coding: utf-8 -*-
"""
Dashboard Router: 教師儀表板 API
提供 Pre-coding 與 CodingHelp 的學生答題情況統計
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from sqlalchemy import select, desc, func
from collections import defaultdict
import logging

from backend.app.agents.debugging.db import (
    engine,
    precoding_question_table,
    precoding_student_answers_table,
    precoding_logic_status_table,
    submission_table,
    practice_table
)
from backend.app.agents.debugging.oj_models import Problem, Session as OJSession

router = APIRouter(prefix="/dashboard", tags=["Teacher Dashboard"])
logger = logging.getLogger(__name__)


# ==========================================
# Problem List API
# ==========================================

@router.get("/problems")
def get_problem_list():
    """
    取得所有題目列表 (供下拉選單使用)
    回傳：problem_id 與 title
    """
    session = OJSession()
    try:
        problems = session.query(Problem.problem_id, Problem.title).order_by(Problem.problem_id.asc()).all()
        return {
            "status": "success",
            "problems": [
                {
                    "problem_id": p.problem_id,
                    "title": p.title or ""
                }
                for p in problems
            ]
        }
    except Exception as e:
        logger.error(f"Get Problem List Error: {e}")
        return {"status": "error", "problems": [], "message": str(e)}
    finally:
        session.close()


# ==========================================
# Helper Functions
# ==========================================

def get_first_attempt_result(responses: List[Dict], question_id: str) -> Optional[Dict]:
    """取得某題的首次作答紀錄"""
    for r in responses:
        if r.get("q_id") == question_id:
            return r
    return None


def get_latest_attempt_result(responses: List[Dict], question_id: str) -> Optional[Dict]:
    """取得某題的最新作答紀錄"""
    latest = None
    for r in responses:
        if r.get("q_id") == question_id:
            latest = r
    return latest


def calculate_first_attempt_score(responses: List[Dict], all_question_ids: List[str]) -> str:
    """計算首答正確率 (幾分之幾)"""
    if not all_question_ids:
        return "0/0"
    
    correct_count = 0
    for qid in all_question_ids:
        first = get_first_attempt_result(responses, qid)
        if first and first.get("is_correct"):
            correct_count += 1
    
    return f"{correct_count}/{len(all_question_ids)}"


# ==========================================
# Pre-coding Dashboard API
# ==========================================

@router.get("/precoding")
def get_precoding_dashboard(problem_id: str = Query(..., description="Problem ID")):
    """
    取得 Pre-coding 儀表板資料
    回傳：
    - students: 學生列表 (包含觀念建構狀態、首答情況、分數)
    - question_stats: 每題的選項分佈統計
    """
    try:
        with engine.connect() as conn:
            # 1. 取得題目資訊
            q_stmt = select(precoding_question_table).where(
                precoding_question_table.c.problem_id == problem_id
            )
            question_row = conn.execute(q_stmt).fetchone()
            
            if not question_row:
                raise HTTPException(status_code=404, detail="Problem not found")
            
            q_data = question_row._mapping
            explain_questions = q_data["explain_code_question"] or []
            error_questions = q_data["error_code_question"] or []
            
            explain_q_ids = [q["id"] for q in explain_questions]
            error_q_ids = [q["id"] for q in error_questions]
            
            # 2. 取得所有學生的 Logic Chat 狀態
            logic_stmt = select(precoding_logic_status_table).where(
                precoding_logic_status_table.c.problem_id == problem_id
            )
            logic_rows = conn.execute(logic_stmt).fetchall()
            logic_status_map = {}
            for row in logic_rows:
                mapping = row._mapping
                logic_status_map[mapping["student_id"]] = mapping["is_completed"]
            
            # 3. 取得所有學生的作答紀錄
            ans_stmt = select(precoding_student_answers_table).where(
                precoding_student_answers_table.c.problem_id == problem_id
            )
            ans_rows = conn.execute(ans_stmt).fetchall()
            
            students = []
            # 統計用
            explain_option_stats = defaultdict(lambda: defaultdict(int))  # {q_id: {option_id: count}}
            error_option_stats = defaultdict(lambda: defaultdict(int))
            
            for row in ans_rows:
                mapping = row._mapping
                student_id = mapping["student_id"]
                explain_responses = mapping["explain_responses"] or []
                error_responses = mapping["error_responses"] or []
                
                # 觀念建構狀態
                logic_completed = logic_status_map.get(student_id, False)
                
                # 程式碼解釋：首答情況
                explain_first_attempts = []
                for qid in explain_q_ids:
                    first = get_first_attempt_result(explain_responses, qid)
                    if first:
                        explain_first_attempts.append({
                            "q_id": qid,
                            "selected_option_id": first.get("selected_option_id"),
                            "is_correct": first.get("is_correct", False)
                        })
                        # 統計選項分佈
                        explain_option_stats[qid][first.get("selected_option_id")] += 1
                
                # 程式除錯：首答情況
                error_first_attempts = []
                for qid in error_q_ids:
                    first = get_first_attempt_result(error_responses, qid)
                    if first:
                        error_first_attempts.append({
                            "q_id": qid,
                            "selected_option_id": first.get("selected_option_id"),
                            "is_correct": first.get("is_correct", False)
                        })
                        error_option_stats[qid][first.get("selected_option_id")] += 1
                
                # 計算分數
                explain_score = calculate_first_attempt_score(explain_responses, explain_q_ids)
                error_score = calculate_first_attempt_score(error_responses, error_q_ids)
                
                # 最終狀態 (使用最新作答判斷)
                explain_final_correct = sum(
                    1 for qid in explain_q_ids 
                    if get_latest_attempt_result(explain_responses, qid) and 
                       get_latest_attempt_result(explain_responses, qid).get("is_correct")
                )
                error_final_correct = sum(
                    1 for qid in error_q_ids 
                    if get_latest_attempt_result(error_responses, qid) and 
                       get_latest_attempt_result(error_responses, qid).get("is_correct")
                )
                
                students.append({
                    "student_id": student_id,
                    "logic_completed": logic_completed,
                    "explain_code": {
                        "first_attempts": explain_first_attempts,
                        "score": explain_score,
                        "final_correct": f"{explain_final_correct}/{len(explain_q_ids)}"
                    },
                    "error_code": {
                        "first_attempts": error_first_attempts,
                        "score": error_score,
                        "final_correct": f"{error_final_correct}/{len(error_q_ids)}"
                    },
                    "is_completed": mapping["progress_stage"] == "completed"
                })
            
            # 4. 整理題目統計
            question_stats = {
                "explain_code": [
                    {
                        "q_id": q["id"],
                        "question_text": q.get("question", {}).get("text", ""),
                        "options": [
                            {
                                "option_id": opt["id"],
                                "label": opt.get("label", ""),
                                "count": explain_option_stats[q["id"]].get(opt["id"], 0)
                            }
                            for opt in q.get("options", [])
                        ]
                    }
                    for q in explain_questions
                ],
                "error_code": [
                    {
                        "q_id": q["id"],
                        "question_text": q.get("question", {}).get("text", ""),
                        "options": [
                            {
                                "option_id": opt["id"],
                                "label": opt.get("label", ""),
                                "count": error_option_stats[q["id"]].get(opt["id"], 0)
                            }
                            for opt in q.get("options", [])
                        ]
                    }
                    for q in error_questions
                ]
            }
            
            return {
                "status": "success",
                "students": students,
                "question_stats": question_stats
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard Precoding Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CodingHelp Dashboard API
# ==========================================

@router.get("/coding_help")
def get_coding_help_dashboard(problem_id: str = Query(..., description="Problem ID")):
    """
    取得 CodingHelp 儀表板資料
    回傳：
    - students: 學生列表 (目前狀態、練習題狀態)
    - verdict_stats: 各 verdict 分佈統計
    """
    try:
        with engine.connect() as conn:
            # 1. 取得所有學生的最新提交
            # 使用子查詢取得每位學生的最新提交
            subq = (
                select(
                    submission_table.c.student_id,
                    func.max(submission_table.c.submitted_at).label("max_time")
                )
                .where(submission_table.c.problem_id == problem_id)
                .group_by(submission_table.c.student_id)
                .subquery()
            )
            
            latest_stmt = (
                select(
                    submission_table.c.student_id,
                    submission_table.c.result,
                    submission_table.c.output
                )
                .join(
                    subq,
                    (submission_table.c.student_id == subq.c.student_id) &
                    (submission_table.c.submitted_at == subq.c.max_time)
                )
                .where(submission_table.c.problem_id == problem_id)
            )
            
            submission_rows = conn.execute(latest_stmt).fetchall()
            
            # 2. 取得練習題狀態
            practice_stmt = select(
                practice_table.c.student_id,
                practice_table.c.answer_is_correct,
                practice_table.c.code_question
            ).where(practice_table.c.problem_id == problem_id)
            
            practice_rows = conn.execute(practice_stmt).fetchall()
            practice_map = {}
            for row in practice_rows:
                mapping = row._mapping
                code_q = mapping["code_question"] or []
                if code_q:  # 空陣列視為 no_practice，不放入 map → 顯示「—」
                    practice_map[mapping["student_id"]] = mapping["answer_is_correct"] or False
            
            # 3. 整理學生資料與統計
            students = []
            verdict_stats = defaultdict(int)  # {verdict: count}
            
            for row in submission_rows:
                mapping = row._mapping
                student_id = mapping["student_id"]
                
                # 解析 verdict
                result = mapping["result"]
                output = mapping["output"]
                
                verdict = "Unknown"
                if output and isinstance(output, dict):
                    verdict = output.get("verdict", "Unknown")
                elif result:
                    # result 可能是 JSON string 或直接字串
                    if isinstance(result, str):
                        verdict = result.strip('"')
                    else:
                        verdict = str(result)
                
                # 標準化 verdict
                if "Accepted" in verdict or "AC" in verdict:
                    verdict = "AC"
                elif "Wrong" in verdict:
                    verdict = "WA"
                elif "Time" in verdict:
                    verdict = "TLE"
                elif "Runtime" in verdict or "Error" in verdict:
                    verdict = "RE"
                
                verdict_stats[verdict] += 1
                
                # 練習題狀態
                practice_completed = practice_map.get(student_id, None)
                practice_status = "no_practice"
                if practice_completed is True:
                    practice_status = "completed"
                elif practice_completed is False:
                    practice_status = "todo"
                
                students.append({
                    "student_id": student_id,
                    "current_verdict": verdict,
                    "practice_status": practice_status
                })
            
            return {
                "status": "success",
                "students": students,
                "verdict_stats": dict(verdict_stats)
            }
            
    except Exception as e:
        logger.error(f"Dashboard CodingHelp Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
