from fastapi import APIRouter, HTTPException, Query, Path, Depends, BackgroundTasks
from typing import Optional, List, Dict, Any
import json, re
import logging
from sqlalchemy import select, desc, insert, update, delete, text, asc, func
from pydantic import BaseModel

# --- OJ & Core Imports ---
from backend.app.agents.debugging.OJ.judge_core import run_judge, compute_verdict
from backend.app.agents.debugging.OJ.queue_manager import submit_queue, analysis_queue
from backend.app.agents.debugging.OJ.rate_limiter import rate_limiter
from backend.app.agents.debugging.OJ.models import CodePayload
from backend.app.agents.debugging.db import (
    load_problem_config, 
    save_submission, 
    get_latest_submission,
    get_submission_count,   
    get_practice_status,    
    update_practice_answer,
    engine,                 
    dialogue_table,         
    evidence_report_table,  
    practice_table,
    submission_table          
)

from backend.app.agents.debugging.oj_models import get_problems_by_chapter, get_problem_by_id
from backend.app.agents.debugging.pre_coding import get_student_precoding_state, process_precoding_submission
from backend.app.agents.debugging.pre_coding.manager import PreCodingManager

# --- Graph Import ---
from backend.app.agents.debugging.graph import app_graph

# --- Help Chat Import (僅用於 /help/chat 端點) ---
from backend.app.agents.debugging.coding_help.help_chat import process_chat

# LangChain Imports (For Chat)
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
import os
from datetime import datetime

router = APIRouter(prefix="/debugging", tags=["Online Judge & Problems"])
logger = logging.getLogger(__name__)

# 初始化 Chat LLM 用於一般對話
chat_llm = ChatOpenAI(model="gpt-4o", temperature=0.3, api_key=os.getenv("OPENAI_API_KEY"))

# ==========================================
# Pydantic Models
# ==========================================

class PreCodingSubmitRequest(BaseModel):
    student_id: str
    problem_id: str
    stage: str               
    question_id: str         
    selected_option_id: int  


class ChatRequest(BaseModel):
    student_id: str
    problem_id: str
    message: str
    submission_num: Optional[int] = None  # V3: Track which submission this chat belongs to

class PracticeAnswerItem(BaseModel):
    q_id: str
    selected_option_id: int

class PracticeSubmitListRequest(BaseModel):
    practice_id: int
    answers: List[PracticeAnswerItem]

class PreCodingChatRequest(BaseModel):
    student_id: str
    problem_id: str
    message: str

def clean_markdown_filter(text: str) -> str:
    """去除字串中的 Markdown 標記語法"""
    if not text:
        return ""
    # 去除粗體、斜體 (**, *, __, _)
    text = re.sub(r'(\*\*|\*|__|_)替換', r'', text) 
    # 更完整的過濾：去除粗體符號但保留文字內容
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text) # 將 **文字** 轉為 文字
    text = re.sub(r'\*(.*?)\*', r'\1', text)     # 將 *文字* 轉為 文字
    # 去除標題符號 (#)
    text = re.sub(r'#+\s?', '', text)
    return text.strip()

# ==========================================
# Helper: Background Task using LangGraph
# ==========================================

async def run_background_graph_task(initial_state: Dict, submission_num: int):
    """
    背景任務：使用 LangGraph app_graph 執行完整的診斷/練習題生成流程。
    根據 is_correct 決定走哪條路：
    - is_correct=False: 執行診斷 -> 路由 -> 檢索(可選) -> 鷹架回覆
    - is_correct=True: 生成練習題
    """
    student_id = initial_state["student_id"]
    problem_id = initial_state["problem_id"]
    is_correct = initial_state.get("is_correct", False)
    
    logger.info(f"Starting background GRAPH task for {student_id} on {problem_id} (Sub#{submission_num}, is_correct={is_correct})")

    try:
        # 執行 LangGraph
        final_state = await app_graph.ainvoke(initial_state)
        
        if is_correct:
            # --- AC 路徑：儲存練習題 ---
            practice_q = final_state.get("practice_question", [])
            
            if practice_q:
                with engine.begin() as conn:
                    conn.execute(insert(practice_table).values(
                        student_id=student_id,
                        problem_id=problem_id,
                        code_question=practice_q,
                        answer_is_correct=False
                    ))
                logger.info(f"Background Task - Practice questions saved for {student_id}")
            else:
                logger.warning(f"No practice questions generated for {student_id}")
        else:
            # --- Error 路徑：儲存診斷報告與鷹架回覆 ---
            report = final_state.get("evidence_report", {})
            scaffold_response = final_state.get("initial_response", "")
            zpd = final_state.get("zpd_level", 1)
            
            # 1. 儲存診斷報告 (Evidence Report) - 包含錯誤程式碼
            with engine.begin() as conn:
                conn.execute(insert(evidence_report_table).values(
                    student_id=student_id,
                    problem_id=problem_id,
                    num=submission_num,
                    evidence_report=report,
                    code={"content": initial_state["current_code"]}
                ))
            
            # 2. 儲存對話紀錄 (使用新的 chat_log 格式)
            if scaffold_response:
                timestamp = datetime.now().isoformat()
                initial_chat_log = [
                    {
                        "role": "agent",
                        "content": clean_markdown_filter(scaffold_response),
                        "zpd": zpd,
                        "timestamp": timestamp,
                        "type": "scaffold"
                    }
                ]
                
                with engine.begin() as conn:
                    conn.execute(insert(dialogue_table).values(
                        student_id=student_id,
                        problem_id=problem_id,
                        num=submission_num,
                        chat_log=initial_chat_log
                    ))
                logger.info(f"Background Task - Diagnosis & Scaffold saved for {student_id}")

    except Exception as e:
        logger.error(f"Background Graph Task Failed: {e}")

# ==========================================
# Online Judge API Endpoints
# ==========================================

@router.post("/submit")
async def submit_code(
    payload: CodePayload,
    background_tasks: BackgroundTasks
):
    # 1. Rate Limit Check
    try:
        rate_limiter.check(payload.student_id)
    except Exception as e:
        raise HTTPException(status_code=429, detail=str(e))

    # 2. Load Problem Config
    problem = load_problem_config(payload.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found.")
    
    # [新增] 檢查截止時間
    now = datetime.now()
    if problem.start_time and now < problem.start_time:
         raise HTTPException(status_code=403, detail="Contest Not Started")
    if problem.end_time and now > problem.end_time:
         raise HTTPException(status_code=403, detail="Time Limit Exceeded: The submission deadline has passed.")
        
    # 3. Execute Judge (必須等待)
    try:
        results = await submit_queue.execute(run_judge, problem, payload.code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Judge failed: {e}")
    
    verdict = compute_verdict(results, len(problem.test_cases))
    
    # 4. Save Submission to DB (必須等待)
    current_count = get_submission_count(payload.student_id, payload.problem_id)
    this_submission_num = current_count + 1 

    try:
        save_submission(
            payload.problem_id,
            payload.student_id,
            payload.code,
            verdict,
            results
        )
    except Exception as e:
        logger.error(f"DB Save Error: {e}")

    # ============================================================
    # Graph State Preparation (Common Logic)
    # ============================================================
    is_correct = "Accepted" in str(verdict) or "AC" in str(verdict)
    
    # 準備錯誤訊息 (Context)
    error_msg = ""
    if not is_correct:
        failed_case = next((r for r in results if r.status != "AC"), None)
        if failed_case:
             error_msg = (
                f"Input: {failed_case.input}\n"
                f"Actual: {failed_case.actual}\n"
                f"Expected: {failed_case.expected}\n"
                f"Error: {failed_case.error}"
            )

    # 取得歷史報告 取最近的3份 (Context)
    previous_reports = []
    try:
        with engine.connect() as conn:
            stmt = select(evidence_report_table.c.evidence_report).where(
                evidence_report_table.c.student_id == payload.student_id,
                evidence_report_table.c.problem_id == payload.problem_id
            ).order_by(desc(evidence_report_table.c.submitted_at)).limit(3)
            result = conn.execute(stmt).fetchall()
            previous_reports = [row[0] for row in result if row[0]]
    except Exception as e:
        logger.warning(f"Failed to fetch previous reports: {e}")

    # 取得題目資訊 (Context)
    problem_info = {}
    try:
        problem_info_raw = get_problem_by_id(payload.problem_id)
        if problem_info_raw:
            problem_info = {
                "title": problem_info_raw.get("title", ""),
                "description": problem_info_raw.get("description", ""),
                "input_description": problem_info_raw.get("input_description", ""),
                "output_description": problem_info_raw.get("output_description", "")
            }
    except Exception as e:
        logger.warning(f"Failed to fetch problem info: {e}")

    # 建構 Graph State
    initial_state = {
        "student_id": payload.student_id,
        "problem_id": payload.problem_id,
        "current_code": payload.code,
        "error_message": error_msg,
        "previous_reports": previous_reports,
        "problem_info": problem_info,
        "is_correct": is_correct,
        "evidence_report": {},
        "search_query": "",
        "retrieved_docs": [],
        "zpd_level": 0,
        "initial_response": "",
        "practice_question": []
    }

    # ============================================================
    # LangGraph 處理邏輯 (Phase 8: 按需生成)
    # ============================================================
    
    # AC (Accepted): 自動觸發練習題生成 (因為學生通常會直接去做練習)
    # Error: 不自動觸發診斷分析 (改為學生切換至「程式修正」分頁時才觸發)
    if is_correct:
        logger.info(f"AC detected. Adding practice generation task to AnalysisQueue.")

        # 先刪除舊的練習題紀錄，確保前端輪詢期間看到 exists=false (顯示"生成中")
        try:
            with engine.begin() as conn:
                conn.execute(
                    delete(practice_table).where(
                        practice_table.c.student_id == payload.student_id,
                        practice_table.c.problem_id == payload.problem_id
                    )
                )
                logger.info(f"Cleared old practice record for {payload.student_id}/{payload.problem_id}")
        except Exception as e:
            logger.error(f"Failed to clear old practice record: {e}")

        # 定義背景任務: 等待分析 → 撈報告 → 生成練習 or 標記無練習
        async def practice_generation_task(student_id, problem_id, submission_num, app_graph_inputs):
            my_task_id = f"{student_id}_{problem_id}_{submission_num}_practice"
            prefix = f"{student_id}_{problem_id}_"

            # Step 1: 檢查是否有正在執行的「程式求救」分析任務，若有則等待
            await analysis_queue.wait_for_prefix(prefix, exclude_task_id=my_task_id, timeout=45)

            # Step 2: 重新撈取 Evidence Reports
            current_reports = []
            try:
                with engine.connect() as conn:
                    stmt = select(evidence_report_table.c.evidence_report).where(
                        evidence_report_table.c.student_id == student_id,
                        evidence_report_table.c.problem_id == problem_id
                    ).order_by(desc(evidence_report_table.c.submitted_at)).limit(5)
                    rows = conn.execute(stmt).fetchall()
                    current_reports = [row[0] for row in rows if row[0]]
            except Exception as e:
                logger.error(f"Practice Gen: Failed to fetch reports: {e}")

            # Step 3: 決定動作
            if current_reports:
                # Case 2.1: 有報告 → 生成練習題
                logger.info(f"Practice Gen: Found {len(current_reports)} report(s). Generating practice questions.")
                app_graph_inputs["previous_reports"] = current_reports
                await run_background_graph_task(app_graph_inputs, submission_num)
            else:
                # Case 2.2: 無報告 → 直接寫入「無練習題」
                logger.info(f"Practice Gen: No reports found. Writing 'No Practice' to DB.")
                try:
                    with engine.begin() as conn:
                        conn.execute(insert(practice_table).values(
                            student_id=student_id,
                            problem_id=problem_id,
                            code_question=[],
                            answer_is_correct=False
                        ))
                except Exception as e:
                    logger.error(f"Practice Gen: Failed to save No-Practice: {e}")

        task_id = f"{payload.student_id}_{payload.problem_id}_{this_submission_num}_practice"
        await analysis_queue.add_task(
            practice_generation_task,
            payload.student_id,
            payload.problem_id,
            this_submission_num,
            initial_state,
            task_id=task_id
        )
    else:
        # Error 路徑：儲存 initial_state 供後續 init_coding_help 使用
        # 實際 AI 分析將在使用者切換至「程式修正」分頁時才觸發
        logger.info(f"Error detected. AI analysis will be triggered on-demand when user accesses coding help.")

    # ============================================================
    # Response
    # ============================================================
    
    response = {
        "verdict": verdict,
        "results": [r.as_dict() for r in results],
        "submission_num": this_submission_num,
    }

    # 訊息
    if is_correct:
        response["message"] = "Accepted! Practice questions are being generated."
    else:
        response["message"] = "Wrong Answer. Click 'Coding Help' for AI assistance."

    return response

# ==========================================
# Other Endpoints (Precoding / History / Chat)
# ==========================================

@router.get("/precoding/{problem_id}")
def get_precoding_status_endpoint(
    problem_id: str, 
    student_id: str = Query(..., description="Student ID")
):
    try:
        return get_student_precoding_state(student_id, problem_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/precoding/submit")
def submit_precoding_answer_endpoint(payload: PreCodingSubmitRequest):
    try:
        # [新增] 檢查時間
        problem = load_problem_config(payload.problem_id)
        if problem:
            now = datetime.now()
            if problem.start_time and now < problem.start_time:
                raise HTTPException(status_code=403, detail="Contest Not Started")
            if problem.end_time and now > problem.end_time:
                raise HTTPException(status_code=403, detail="Time Limit Exceeded")

        result = process_precoding_submission(
            payload.student_id, 
            payload.problem_id, 
            payload.stage, 
            payload.question_id, 
            payload.selected_option_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# Pre-Coding Chatbot API (新增：對話式引導)
# ==========================================

@router.get("/precoding/logic/status/{problem_id}")
def get_precoding_logic_status_endpoint(
    problem_id: str, 
    student_id: str = Query(..., description="Student ID")
):
    """取得學生在 Pre-Coding Logic 階段的狀態（對話紀錄與進度）"""
    try:
        session = PreCodingManager.get_or_create_session(student_id, problem_id)
        return {
            "status": "success",
            "data": session
        }
    except Exception as e:
        logger.error(f"PreCoding Logic Status Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/precoding/logic/chat")
async def precoding_logic_chat_endpoint(payload: PreCodingChatRequest):
    """處理學生的聊天訊息（Pre-Coding Logic 階段）"""
    try:
        # [新增] 檢查時間
        problem = load_problem_config(payload.problem_id)
        if problem:
            now = datetime.now()
            if problem.start_time and now < problem.start_time:
                raise HTTPException(status_code=403, detail="Contest Not Started")
            if problem.end_time and now > problem.end_time:
                raise HTTPException(status_code=403, detail="Time Limit Exceeded")

        result = await PreCodingManager.process_chat(
            payload.student_id, 
            payload.problem_id, 
            payload.message
        )
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        logger.error(f"PreCoding Logic Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/student_code/{student_id}/{problem_id}")
def get_student_code_endpoint(student_id: str, problem_id: str):
    """獲取學生最新提交狀態"""
    try:
        submission = get_latest_submission(student_id, problem_id)
        
        code_content = ""
        result_display = ""
        is_accepted = False
        
        if submission:
            raw_code = submission["code"]
            if isinstance(raw_code, dict):
                code_content = raw_code.get("content", "")
            elif isinstance(raw_code, str):
                try:
                    code_json = json.loads(raw_code)
                    code_content = code_json.get("content", "")
                except:
                    code_content = raw_code
            
            output_data = submission["output"]
            if output_data and isinstance(output_data, dict):
                verdict = output_data.get("verdict", "Unknown")
                result_display = verdict
                if "Accepted" in verdict or "AC" in verdict:
                    is_accepted = True
            else:
                raw_res = str(submission["result"])
                result_display = raw_res.strip('"')
                if "Accepted" in raw_res or "AC" in raw_res:
                    is_accepted = True

        practice_info = get_practice_status(student_id, problem_id)

        # Calculate submission_num for frontend
        sub_num = get_submission_count(student_id, problem_id)

        # Calculate latest_report_num for frontend (V3)
        latest_report_num = 0
        try:
            with engine.connect() as conn:
                stmt = select(func.max(evidence_report_table.c.num)).where(
                    evidence_report_table.c.student_id == student_id,
                    evidence_report_table.c.problem_id == problem_id
                )
                row = conn.execute(stmt).fetchone()
                if row and row[0]:
                    latest_report_num = row[0]
        except Exception as e:
            logger.warning(f"Failed to get latest report num: {e}")

        return {
            "status": "success",
            "data": {
                "code": code_content,
                "result": result_display, 
                "is_accepted": is_accepted,
                "practice": practice_info,
                "submitted_at": submission["submitted_at"] if submission else None,
                "submission_num": sub_num,
                "latest_report_num": latest_report_num
            }
        }

    except Exception as e:
        logger.error(f"Error getting student code: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/problems/chapter/{chapter_id}")
def list_problems_by_chapter_endpoint(
    chapter_id: str = Path(...),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None)
):
    try:
        return get_problems_by_chapter(chapter_id, start_time=start_time, end_time=end_time)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/problems/{problem_id}")
def get_problem_endpoint(problem_id: str = Path(...)):
    try:
        problem = get_problem_by_id(problem_id)
        if not problem:
            raise HTTPException(status_code=404, detail="Problem not found")
        return problem
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/practice/submit")
def submit_practice_answer_endpoint(payload: PracticeSubmitListRequest):
    try:
        with engine.connect() as conn:
            stmt = select(practice_table.c.code_question).where(practice_table.c.id == payload.practice_id)
            row = conn.execute(stmt).fetchone()
            
        if not row:
            raise HTTPException(status_code=404, detail="Practice session not found")
            
        questions_list = row._mapping["code_question"]
        
        q_map = {}
        for q in questions_list:
            q_id = q.get("id")
            correct_id = q.get("answer_config", {}).get("correct_id")
            q_map[q_id] = correct_id
            
        results = []
        all_correct = True
        
        for ans in payload.answers:
            correct_id = q_map.get(ans.q_id)
            is_correct = (ans.selected_option_id == correct_id)
            if not is_correct:
                all_correct = False
                
            results.append({
                "q_id": ans.q_id,
                "is_correct": is_correct,
                "selected_option_id": ans.selected_option_id
            })
            
        update_practice_answer(
            payload.practice_id, 
            results, 
            all_correct
        )
        
        return {
            "status": "success",
            "all_correct": all_correct,
            "results": results 
        }

    except Exception as e:
        logger.error(f"Practice Submit Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class InitHelpRequest(BaseModel):
    student_id: str
    problem_id: str
    force_refresh: Optional[bool] = False
    submission_num: Optional[int] = None # V3: Snapshot Analysis

@router.post("/help/init")
async def init_coding_help(payload: InitHelpRequest):
    """
    初始化 CodingHelp (Phase 8: 按需生成)
    - 可指定 submission_num 進行 Snapshot Analysis
    """
    try:
        latest_count = get_submission_count(payload.student_id, payload.problem_id)
        if latest_count == 0:
             raise HTTPException(status_code=404, detail="No submission found.")
             
        # Determine Target Num
        target_num = payload.submission_num
        if target_num is None or target_num == 0:
            target_num = latest_count
        
        # Ensure target doesn't exceed latest
        if target_num > latest_count:
             target_num = latest_count

        logger.info(f"Init Coding Help for {payload.student_id} on {payload.problem_id}, Target Num: {target_num} (Latest: {latest_count})")

        with engine.connect() as conn:
            # Force Refresh: Clear old data for TARGET num
            if payload.force_refresh:
                logger.info(f"Force Refresh detected for {payload.student_id} on {payload.problem_id} (Sub#{target_num}). Clearing old data.")
                with engine.begin() as trans_conn:
                     trans_conn.execute(dialogue_table.delete().where(
                         dialogue_table.c.student_id == payload.student_id,
                         dialogue_table.c.problem_id == payload.problem_id,
                         dialogue_table.c.num == target_num
                     ))
                     trans_conn.execute(evidence_report_table.delete().where(
                         evidence_report_table.c.student_id == payload.student_id,
                         evidence_report_table.c.problem_id == payload.problem_id,
                         evidence_report_table.c.num == target_num
                     ))
            
            # 1. 檢查是否已有對話紀錄 (Target Num)
            if not payload.force_refresh:
                check_stmt = select(dialogue_table).where(
                    dialogue_table.c.student_id == payload.student_id,
                    dialogue_table.c.problem_id == payload.problem_id,
                    dialogue_table.c.num == target_num
                ).limit(1)
                existing_dialogue = conn.execute(check_stmt).fetchone()
                
                if existing_dialogue:
                    mapping = existing_dialogue._mapping
                    chat_log = mapping.get("chat_log") or []
                    
                    initial_reply = ""
                    zpd_level = 1
                    
                    if chat_log:
                        for msg in reversed(chat_log):
                            if msg.get("role") == "agent":
                                initial_reply = msg.get("content", "")
                                zpd_level = msg.get("zpd", 1)
                                break
                    
                    return {
                        "status": "resumed",
                        "reply": initial_reply,
                        "zpd_level": zpd_level,
                        "num": target_num,
                        "chat_log": chat_log
                    }
            
            # 2. 檢查 Evidence Report (Target Num)
            check_report_stmt = select(evidence_report_table).where(
                evidence_report_table.c.student_id == payload.student_id,
                evidence_report_table.c.problem_id == payload.problem_id,
                evidence_report_table.c.num == target_num
            ).limit(1)
            existing_report = conn.execute(check_report_stmt).fetchone()
            
            task_id = f"{payload.student_id}_{payload.problem_id}_{target_num}"
            
            if existing_report:
                if analysis_queue.is_processing(task_id):
                    return {
                        "status": "pending", 
                        "message": "AI diagnosis is ready. Initializing chat...",
                        "num": target_num
                    }
                else:
                    logger.warning(f"Report exists but no dialogue, and task {task_id} is not running. Re-triggering.")
        
        # 3. Trigger Analysis for TARGET Submission
        logger.info(f"On-Demand Analysis Triggered for {payload.student_id} on {payload.problem_id} (Num#{target_num})")
        
        # query specific submission by offset
        # num 1 is offset 0
        offset_val = target_num - 1
        logger.info(f"Fetching submission with offset {offset_val} (TargetNum: {target_num})")
        
        stmt_sub = select(submission_table).where(
            submission_table.c.student_id == payload.student_id,
            submission_table.c.problem_id == payload.problem_id
        ).order_by(asc(submission_table.c.submitted_at)).offset(offset_val).limit(1)

        with engine.connect() as conn:
             submission_row = conn.execute(stmt_sub).fetchone()
        
        target_submission = None
        if submission_row:
             mapping = submission_row._mapping
             target_submission = {
                 "code": mapping["code"],
                 "output": mapping["output"],
                 "submitted_at": mapping["submitted_at"]
             }
             logger.info(f"Snapshot Submission Found: Time={mapping['submitted_at']}")
        else:
             # Fallback
             logger.warning(f"Submission #{target_num} not found via offset {offset_val}. Falling back to latest.")
             target_submission = get_latest_submission(payload.student_id, payload.problem_id)

        if not target_submission:
             raise HTTPException(status_code=404, detail="Submission data not found.")
        
        # Parse Code
        raw_code = target_submission["code"]
        if isinstance(raw_code, dict):
            code_content = raw_code.get("content", "")
        elif isinstance(raw_code, str):
            try:
                import json as json_module
                code_json = json_module.loads(raw_code)
                code_content = code_json.get("content", "")
            except:
                code_content = raw_code
        else:
            code_content = str(raw_code)
            
        logger.info(f"Snapshot Code Preview (First 50 chars): {code_content[:50]}...")
        
        # Error Msg
        error_msg = ""
        output_data = target_submission.get("output", {})
        if isinstance(output_data, dict):
            results_list = output_data.get("results", [])
            for r in results_list:
                if r.get("status") != "AC":
                    error_msg = (
                        f"Input: {r.get('input', '')}\n"
                        f"Actual: {r.get('actual', '')}\n"
                        f"Expected: {r.get('expected', '')}\n"
                        f"Error: {r.get('error', '')}"
                    )
                    break
        
        # Previous Reports (Context)
        previous_reports = []
        try:
            with engine.connect() as conn2:
                stmt = select(evidence_report_table.c.evidence_report).where(
                    evidence_report_table.c.student_id == payload.student_id,
                    evidence_report_table.c.problem_id == payload.problem_id
                ).order_by(desc(evidence_report_table.c.submitted_at)).limit(3)
                result = conn2.execute(stmt).fetchall()
                previous_reports = [row[0] for row in result if row[0]]
        except Exception as e:
            logger.warning(f"Failed to fetch previous reports: {e}")
        
        problem_info = {}
        try:
            problem_info_raw = get_problem_by_id(payload.problem_id)
            if problem_info_raw:
                problem_info = {
                    "title": problem_info_raw.get("title", ""),
                    "description": problem_info_raw.get("description", ""),
                    "input_description": problem_info_raw.get("input_description", ""),
                    "output_description": problem_info_raw.get("output_description", "")
                }
        except Exception as e:
            logger.warning(f"Failed to fetch problem info: {e}")
        
        initial_state = {
            "student_id": payload.student_id,
            "problem_id": payload.problem_id,
            "current_code": code_content,
            "error_message": error_msg,
            "previous_reports": previous_reports,
            "problem_info": problem_info,
            "is_correct": False,
            "evidence_report": {},
            "search_query": "",
            "retrieved_docs": [],
            "zpd_level": 0,
            "initial_response": "",
            "practice_question": []
        }
        
        task_id = f"{payload.student_id}_{payload.problem_id}_{target_num}"
        
        added = await analysis_queue.add_task(
            run_background_graph_task,
            initial_state,
            target_num,
            task_id=task_id
        )
        
        if not added:
            logger.info(f"Task {task_id} is already processing. Returning pending.")
            return {
                "status": "pending",
                "message": "AI diagnosis is already processing...",
                "num": target_num
            }
        
        return {
            "status": "started",
            "message": "AI analysis has been triggered. Please poll for results.",
            "num": target_num
        }

    except Exception as e:
        logger.error(f"CodingHelp Init Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/help/chat")
async def chat_with_agent(payload: ChatRequest):
    """
    處理聊天請求
    使用新的 help_chat 模組，包含 Input Guard 和 chat_log 格式
    """
    try:
        latest_num = get_submission_count(payload.student_id, payload.problem_id)
        # V3: Use submission_num from request if provided, else fall back to latest_num
        target_num = payload.submission_num if (payload.submission_num is not None and payload.submission_num > 0) else latest_num
        logger.info(f"Chat for {payload.student_id} on {payload.problem_id}, using num={target_num} (latest={latest_num})")
        
        with engine.connect() as conn:
            # 1. 取得 evidence report (for TARGET num)
            stmt_rep = select(evidence_report_table).where(
                evidence_report_table.c.student_id == payload.student_id,
                evidence_report_table.c.problem_id == payload.problem_id,
                evidence_report_table.c.num == target_num
            )
            report_row = conn.execute(stmt_rep).fetchone()
            
            context_report = {}
            if report_row:
                context_report = report_row._mapping["evidence_report"]
            
            # 2. 取得現有對話紀錄 (for TARGET num)
            stmt_dial = select(dialogue_table).where(
                dialogue_table.c.student_id == payload.student_id,
                dialogue_table.c.problem_id == payload.problem_id,
                dialogue_table.c.num == target_num
            ).limit(1)
            dialogue_row = conn.execute(stmt_dial).fetchone()
            
            existing_chat_log = []
            zpd_val = 1
            dialogue_id = None
            
            if dialogue_row:
                mapping = dialogue_row._mapping
                existing_chat_log = mapping.get("chat_log") or []
                dialogue_id = mapping.get("id")
                
                # 從 chat_log 取得 zpd_level
                if existing_chat_log:
                    for msg in existing_chat_log:
                        if msg.get("zpd"):
                            zpd_val = msg.get("zpd", 1)
                            break
        
        # 3. 取得題目資訊
        problem_info_raw = get_problem_by_id(payload.problem_id)
        problem_info = {
            "title": problem_info_raw.get("title", ""),
            "description": problem_info_raw.get("description", ""),
            "input_description": problem_info_raw.get("input_description", ""),
            "output_description": problem_info_raw.get("output_description", "")
        }
        
        # 4. 使用 help_chat 模組處理對話
        chat_result = await process_chat(
            message=payload.message,
            zpd_level=zpd_val,
            evidence_report=context_report,
            problem_info=problem_info,
            chat_log=existing_chat_log,
            student_id=payload.student_id,
            problem_id=payload.problem_id,
        )
        
        # 5. 檢查輸入驗證結果
        if not chat_result["is_valid"]:
            return {
                "reply": chat_result["response"],
                "is_valid": False
            }
        
        # 6. 更新對話紀錄 (使用 UPDATE 或 INSERT)
        updated_chat_log = chat_result["updated_chat_log"]
        
        if dialogue_id:
            # 更新現有記錄
            with engine.begin() as conn:
                conn.execute(
                    update(dialogue_table).where(
                        dialogue_table.c.id == dialogue_id
                    ).values(
                        chat_log=updated_chat_log
                    )
                )
        else:
            # 新增記錄 (如果不存在) - use target_num, not latest_num
            with engine.begin() as conn:
                conn.execute(insert(dialogue_table).values(
                    student_id=payload.student_id,
                    problem_id=payload.problem_id,
                    num=target_num,
                    chat_log=updated_chat_log
                ))

        return {
            "reply": chat_result["response"],
            "is_valid": True,
            "chat_log": updated_chat_log
        }

    except Exception as e:
        logger.error(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/help/history/{student_id}/{problem_id}")
def get_history_endpoint(
    student_id: str, 
    problem_id: str,
    submission_num: Optional[int] = Query(None, description="Target submission number")
):
    """取得對話歷史 (僅使用 chat_log 格式)"""
    try:
        latest_num = get_submission_count(student_id, problem_id)
        if latest_num == 0:
            return {"chat_log": []}

        # V3: Use submission_num if provided, else latest
        target_num = submission_num if (submission_num is not None and submission_num > 0) else latest_num

        with engine.connect() as conn:
            stmt = select(dialogue_table).where(
                dialogue_table.c.student_id == student_id,
                dialogue_table.c.problem_id == problem_id,
                dialogue_table.c.num == target_num 
            ).order_by(dialogue_table.c.id.asc())
            rows = conn.execute(stmt).fetchall()
            
            # V3 Fallback: If no dialogue found for target_num, get the latest available
            if not rows:
                logger.info(f"No dialogue found for num={target_num}, falling back to latest available")
                # Find the latest num that has dialogue
                max_num_stmt = select(func.max(dialogue_table.c.num)).where(
                    dialogue_table.c.student_id == student_id,
                    dialogue_table.c.problem_id == problem_id,
                )
                max_row = conn.execute(max_num_stmt).fetchone()
                if max_row and max_row[0]:
                    fallback_num = max_row[0]
                    logger.info(f"Found latest dialogue at num={fallback_num}")
                    stmt_fallback = select(dialogue_table).where(
                        dialogue_table.c.student_id == student_id,
                        dialogue_table.c.problem_id == problem_id,
                        dialogue_table.c.num == fallback_num,
                    ).order_by(dialogue_table.c.id.asc())
                    rows = conn.execute(stmt_fallback).fetchall()
        
        # 回傳 chat_log 格式
        all_chat_log = []
        
        for r in rows:
            mapping = r._mapping
            chat_log = mapping.get("chat_log") or []
            if chat_log:
                all_chat_log.extend(chat_log)
        
        return {"chat_log": all_chat_log}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))