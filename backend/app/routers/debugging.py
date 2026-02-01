from fastapi import APIRouter, HTTPException, Query, Path, Depends, BackgroundTasks
from typing import Optional, List, Dict, Any
import json, re
import logging
from sqlalchemy import select, desc, insert, text
from pydantic import BaseModel

# --- OJ & Core Imports ---
from backend.app.agents.debugging.OJ.judge_core import run_judge, compute_verdict
from backend.app.agents.debugging.OJ.queue_manager import submit_queue
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
    practice_table          
)

from backend.app.agents.debugging.oj_models import get_problems_by_chapter, get_problem_by_id
from backend.app.agents.debugging.pre_coding import get_student_precoding_state, process_precoding_submission
from backend.app.agents.debugging.pre_coding.manager import PreCodingManager

# --- Graph Import ---
from backend.app.agents.debugging.graph import app_graph

# LangChain Imports (For Chat)
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
import os

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

class InitHelpRequest(BaseModel):
    student_id: str
    problem_id: str

class ChatRequest(BaseModel):
    student_id: str
    problem_id: str
    message: str

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
# Helper: Background Task for Error Diagnosis
# ==========================================

async def run_background_diagnosis_task(initial_state: Dict, submission_num: int):
    """
    背景任務：僅針對「錯誤提交」執行 AI 診斷、RAG 檢索與鷹架生成。
    """
    student_id = initial_state["student_id"]
    problem_id = initial_state["problem_id"]
    logger.info(f"Starting background DIAGNOSIS for {student_id} on {problem_id} (Sub#{submission_num})")

    try:
        # 執行 Graph
        final_state = await app_graph.ainvoke(initial_state)
        
        # 取得結果
        report = final_state.get("evidence_report", {})
        scaffold_response = final_state.get("initial_response", "")
        zpd = final_state.get("zpd_level", 1)

        # 1. 儲存診斷報告 (Evidence Report)
        with engine.begin() as conn:
            conn.execute(insert(evidence_report_table).values(
                student_id=student_id,
                problem_id=problem_id,
                num=submission_num,
                evidence_report=report,
                code={"content": initial_state["current_code"]}
            ))
        
        # 2. 儲存自動生成的對話鷹架 (Scaffold)
        if scaffold_response:
            with engine.begin() as conn:
                conn.execute(insert(dialogue_table).values(
                    student_id=student_id,
                    problem_id=problem_id,
                    num=submission_num, 
                    student_question=None, 
                    agent_reply={"content": clean_markdown_filter(scaffold_response), "type": "scaffold"},
                    zpd_level=zpd
                ))
            logger.info(f"Background Task - Diagnosis & Scaffold saved for {student_id}")

    except Exception as e:
        logger.error(f"Background Diagnosis Failed: {e}")

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
    # Branching Logic: Sync for AC, Async for Error
    # ============================================================
    
    practice_question_data = []

    if is_correct:
        # --- Case A: Accepted (同步等待) ---
        # 因為前端要立刻拿到練習題，所以這裡使用 await 等待 Graph 執行完畢
        try:
            logger.info(f"Verdict is AC. Generating practice questions synchronously...")
            final_state = await app_graph.ainvoke(initial_state)
            
            practice_q = final_state.get("practice_question", [])
            
            if practice_q:
                # 寫入 Practice Table
                with engine.begin() as conn:
                    conn.execute(insert(practice_table).values(
                        student_id=payload.student_id,
                        problem_id=payload.problem_id,
                        code_question=practice_q,
                        answer_is_correct=False
                    ))
                practice_question_data = practice_q
                logger.info("Practice questions generated and saved.")
        except Exception as e:
            logger.error(f"Sync Practice Generation Failed: {e}")
            # 即使生成練習題失敗，仍應回傳 AC 結果，不拋錯
    
    else:
        # --- Case B: Error (背景執行) ---
        # 前端不需要立刻拿到診斷結果，放入 BackgroundTasks
        background_tasks.add_task(
            run_background_diagnosis_task,
            initial_state=initial_state,
            submission_num=this_submission_num
        )

    # ============================================================
    # Response
    # ============================================================
    
    response = {
        "verdict": verdict,
        "results": [r.as_dict() for r in results],
        "submission_num": this_submission_num,
    }

    # 如果是 AC 且有生成練習題，放入回傳物件
    if is_correct and practice_question_data:
        response["practice_question"] = practice_question_data
    
    # 如果是 Error，給個提示訊息
    if not is_correct:
        response["message"] = "Diagnosis is processing in background."

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

        return {
            "status": "success",
            "data": {
                "code": code_content,
                "result": result_display, 
                "is_accepted": is_accepted,
                "practice": practice_info,
                "submitted_at": submission["submitted_at"] if submission else None
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

@router.post("/help/init")
async def init_coding_help(payload: InitHelpRequest):
    try:
        latest_num = get_submission_count(payload.student_id, payload.problem_id)
        if latest_num == 0:
             raise HTTPException(status_code=404, detail="No submission found.")
        
        with engine.connect() as conn:
            check_stmt = select(dialogue_table).where(
                dialogue_table.c.student_id == payload.student_id,
                dialogue_table.c.problem_id == payload.problem_id,
                dialogue_table.c.num == latest_num
            ).limit(1)
            existing_dialogue = conn.execute(check_stmt).fetchone()
            
            if existing_dialogue:
                return {
                    "status": "resumed",
                    "reply": existing_dialogue._mapping["agent_reply"]["content"],
                    "zpd_level": existing_dialogue._mapping["zpd_level"],
                    "num": latest_num
                }
            
            return {
                "status": "pending", 
                "message": "AI diagnosis is still processing. Please check back shortly."
            }

    except Exception as e:
        logger.error(f"CodingHelp Init Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/help/chat")
async def chat_with_agent(payload: ChatRequest):
    try:
        latest_num = get_submission_count(payload.student_id, payload.problem_id)
        
        with engine.connect() as conn:
            # evidence report
            stmt_rep = select(evidence_report_table).where(
                evidence_report_table.c.student_id == payload.student_id,
                evidence_report_table.c.problem_id == payload.problem_id,
                evidence_report_table.c.num == latest_num
            )
            report_row = conn.execute(stmt_rep).fetchone()
            
            context_report = {}
            if report_row:
                context_report = report_row._mapping["evidence_report"]
            
            # zpd level
            stmt_zpd = select(dialogue_table.c.zpd_level).where(
                 dialogue_table.c.student_id == payload.student_id,
                 dialogue_table.c.problem_id == payload.problem_id,
                 dialogue_table.c.num == latest_num
            ).limit(1)
            zpd_val = conn.execute(stmt_zpd).scalar() or 1

            # dialogue history (前一個回覆 & 學生現在提問)
            stmt_dial = (
                select(dialogue_table)
                .where(
                    dialogue_table.c.student_id == payload.student_id,
                    dialogue_table.c.problem_id == payload.problem_id
                )
                .order_by(dialogue_table.c.id.desc())  
                .limit(2)                             
            )

            history_rows = conn.execute(stmt_dial).fetchall() 

        problem_info_raw = get_problem_by_id(payload.problem_id)
        problem_context = f"Problem: {problem_info_raw.get('title')}\nDesc: {problem_info_raw.get('description')}"
        zpd, strategy = (1, "引導學生思考修正邏輯，可提供部分範例。") if zpd_val == 1 else (2, "給予具體提示。") if zpd_val == 2 else (3, "僅給予方向性提示。")

        messages = [
            SystemMessage(content=f"""
            你是一位程式設計輔導老師，請根據前一個回覆和學生現在提問，提供適當的引導。

            題目資訊：{problem_context}**注意**:輸出格式需參考sampls
            學生錯誤程式碼診斷結果：{json.dumps(context_report)}
            
            【教學策略 (ZPD 等級 {zpd})】: {strategy}

            請遵守：
            1. 使用繁體中文，**簡單明瞭**，條列式回覆，不帶任何情緒。
            2. 嚴禁使用 Markdown 語法。
            3. 依照策略強度提供引導，不要直接給出完整正確答案。
            4. **不可回答與題目無相關問題**

            """)
        ]

        for row in history_rows:
            d = row._mapping
            if d["student_question"]:
                messages.append(HumanMessage(content=d["student_question"]["content"]))
            if d["agent_reply"]:
                messages.append(AIMessage(content=d["agent_reply"]["content"]))
        
        messages.append(HumanMessage(content=payload.message))

        response = await chat_llm.ainvoke(messages)
        clean_reply = clean_markdown_filter(response.content)
        with engine.begin() as conn:
            conn.execute(insert(dialogue_table).values(
                student_id=payload.student_id,
                problem_id=payload.problem_id,
                num=latest_num, 
                student_question={"content": payload.message},
                agent_reply={"content": clean_reply, "type": "chat"},
                zpd_level=zpd_val
            ))

        return {"reply": clean_reply}

    except Exception as e:
        logger.error(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/help/history/{student_id}/{problem_id}")
def get_history_endpoint(student_id: str, problem_id: str):
    try:
        latest_num = get_submission_count(student_id, problem_id)
        if latest_num == 0:
            return []

        with engine.connect() as conn:
            stmt = select(dialogue_table).where(
                dialogue_table.c.student_id == student_id,
                dialogue_table.c.problem_id == problem_id,
                dialogue_table.c.num == latest_num 
            ).order_by(dialogue_table.c.id.asc())
            rows = conn.execute(stmt).fetchall()
            
        return [
            {
                "id": r._mapping["id"],
                "num": r._mapping["num"],
                "student": r._mapping["student_question"],
                "agent": r._mapping["agent_reply"],
                "zpd": r._mapping["zpd_level"],
                "time": r._mapping["submitted_at"]
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))