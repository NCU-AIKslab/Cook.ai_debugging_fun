from fastapi import HTTPException
from sqlalchemy import select, insert, update, and_
from datetime import datetime
from typing import Dict, Any, List

# 從 db.py 引入 engine 和表格定義
from .db import engine, precoding_question_table, precoding_student_answers_table

def sanitize_question_data(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    資料淨化：移除前端不該看到的答案 (answer_config) 與選項回饋 (feedback)。
    只保留 id, type, question, options(id, label)。
    """
    if not questions:
        return []
    
    sanitized_list = []
    for q in questions:
        q_copy = q.copy()
        
        # 移除正確答案設定
        if "answer_config" in q_copy:
            del q_copy["answer_config"]
            
        # 處理選項：移除 feedback，只留 id 和 label
        if "options" in q_copy and isinstance(q_copy["options"], list):
            clean_options = []
            for opt in q_copy["options"]:
                clean_opt = {
                    "id": opt.get("id"),
                    "label": opt.get("label")
                    # 不包含 feedback
                }
                clean_options.append(clean_opt)
            q_copy["options"] = clean_options
            
        sanitized_list.append(q_copy)
    
    return sanitized_list

def get_student_precoding_state(student_id: str, problem_id: str) -> Dict[str, Any]:
    with engine.connect() as conn:
        # 1. 獲取題目資訊
        q_stmt = select(precoding_question_table).where(
            precoding_question_table.c.problem_id == problem_id
        )
        question_row = conn.execute(q_stmt).fetchone()

        if not question_row:
            raise HTTPException(status_code=404, detail="Pre-coding question not found")
        
        question_data = question_row._mapping if hasattr(question_row, "_mapping") else question_row

        # 2. 獲取或初始化學生作答紀錄
        a_stmt = select(precoding_student_answers_table).where(
            and_(
                precoding_student_answers_table.c.student_id == student_id,
                precoding_student_answers_table.c.problem_id == problem_id
            )
        )
        answer_row = conn.execute(a_stmt).fetchone()

        if not answer_row:
            conn.execute(
                insert(precoding_student_answers_table).values(
                    student_id=student_id,
                    problem_id=problem_id,
                    progress_stage="logic",
                    logic_responses=[],
                    error_responses=[],
                    explain_responses=[] # [New] 初始化
                )
            )
            conn.commit()
            answer_row = conn.execute(a_stmt).fetchone()

        answer_data = answer_row._mapping if hasattr(answer_row, "_mapping") else answer_row

        # 3. 處理回傳資料 (淨化 JSON)
        raw_logic_qs = question_data["logic_question"] or []
        raw_error_qs = question_data["error_code_question"] or []
        raw_explain_qs = question_data["explain_code_question"] or [] # [New]

        response = {
            "current_stage": answer_data["progress_stage"],
            "is_completed": answer_data["progress_stage"] == "completed",
            
            "student_status": {
                "logic": answer_data["logic_responses"] or [],
                "error_code": answer_data["error_responses"] or [],
                "explain_code": answer_data["explain_responses"] or [] # [New]
            },
            
            "question_data": {
                "logic_question": sanitize_question_data(raw_logic_qs),
                "error_code_question": sanitize_question_data(raw_error_qs),
                "explain_code_question": sanitize_question_data(raw_explain_qs) # [New]
            },
            "template": None
        }

        if answer_data["progress_stage"] == "completed":
            response["template"] = question_data["correct_code_template"]

        return response


def process_precoding_submission(
    student_id: str, 
    problem_id: str, 
    stage: str, 
    question_id: str,         
    selected_option_id: int   
) -> Dict[str, Any]:
    
    with engine.connect() as conn:
        # 1. 讀取題目
        q_stmt = select(precoding_question_table).where(
            precoding_question_table.c.problem_id == problem_id
        )
        question_row = conn.execute(q_stmt).fetchone()
        if not question_row:
            raise HTTPException(status_code=404, detail="Problem not found")
        
        q_data = question_row._mapping if hasattr(question_row, "_mapping") else question_row
        
        # 2. 讀取學生狀態
        a_stmt = select(precoding_student_answers_table).where(
            and_(
                precoding_student_answers_table.c.student_id == student_id,
                precoding_student_answers_table.c.problem_id == problem_id
            )
        )
        answer_row = conn.execute(a_stmt).fetchone()
        if not answer_row:
            raise HTTPException(status_code=400, detail="Student record not found")
        
        a_data = answer_row._mapping if hasattr(answer_row, "_mapping") else answer_row
        
        current_stage = a_data["progress_stage"]
        new_stage = current_stage
        
        # 3. 確定要處理的題目列表
        target_questions = []
        response_column = ""

        if stage == "logic":
            target_questions = q_data["logic_question"] or []
            response_column = "logic_responses"
        elif stage == "error_code":
            if current_stage == "logic":
                 raise HTTPException(status_code=403, detail="Logic stage not passed yet")
            target_questions = q_data["error_code_question"] or []
            response_column = "error_responses"
        elif stage == "explain_code": # [New]
            if current_stage in ["logic", "error_code"]:
                 raise HTTPException(status_code=403, detail="Previous stages not passed yet")
            target_questions = q_data["explain_code_question"] or []
            response_column = "explain_responses"
        else:
            raise HTTPException(status_code=400, detail="Invalid stage")

        # 4. 尋找對應的題目 (ByKey: id)
        target_q = next((q for q in target_questions if q["id"] == question_id), None)
        if not target_q:
            raise HTTPException(status_code=404, detail=f"Question ID '{question_id}' not found in stage {stage}")

        # 5. 判斷對錯
        answer_config = target_q.get("answer_config", {})
        correct_id = answer_config.get("correct_id")
        is_correct = (selected_option_id == correct_id)
        
        # 6. 取得回饋 (Feedback)
        options = target_q.get("options", [])
        selected_opt = next((opt for opt in options if opt["id"] == selected_option_id), None)
        feedback = selected_opt.get("feedback", "") if selected_opt else "Invalid option selected"
        explanation = answer_config.get("explanation", "")

        # 7. 更新作答紀錄 (JSONB List)
        current_responses = list(a_data[response_column] or [])
        
        # 移除舊的該題作答
        current_responses = [r for r in current_responses if r.get("q_id") != question_id]
        
        # 加入新作答
        current_responses.append({
            "q_id": question_id,
            "selected_option_id": selected_option_id,
            "is_correct": is_correct
        })
        
        # 8. 檢查該階段是否「全部完成」
        all_q_ids = [q["id"] for q in target_questions]
        correct_q_ids = [r["q_id"] for r in current_responses if r.get("is_correct") is True]
        
        is_stage_cleared = all(qid in correct_q_ids for qid in all_q_ids)
        
        if is_stage_cleared:
            if stage == "logic":
                new_stage = "error_code"
            elif stage == "error_code":
                new_stage = "explain_code" # [New] 進入解釋階段
            elif stage == "explain_code":
                new_stage = "completed"    # [New] 全部完成

        # 9. 寫入資料庫
        update_values = {
            response_column: current_responses,
            "progress_stage": new_stage,
            "submitted_at": datetime.now()
        }

        conn.execute(
            update(precoding_student_answers_table).where(
                and_(
                    precoding_student_answers_table.c.student_id == student_id,
                    precoding_student_answers_table.c.problem_id == problem_id
                )
            ).values(**update_values)
        )
        conn.commit()

        # 10. 回傳結果
        return {
            "is_correct": is_correct,
            "feedback": feedback,
            "explanation": explanation,
            "next_stage": new_stage,
            "stage_completed": is_stage_cleared
        }