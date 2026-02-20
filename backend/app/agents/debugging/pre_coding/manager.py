"""
Pre-Coding Manager Module

This module contains the main manager class that coordinates the pre-coding
chatbot flow, including session management and stage transitions.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, insert, update, and_

from ..db import (
    engine, 
    precoding_logic_status_table, 
    precoding_logic_logs_table,
    precoding_student_answers_table  # Legacy table for 403 fix
)
from ..oj_models import get_problem_by_id
from .agents import UnderstandingAgent, DecompositionAgent, InputFilterAgent, generate_opening_question


class PreCodingManager:
    """
    Pre-Coding 對話式引導的主管理器。
    負責：
    1. Session 初始化與狀態管理
    2. 協調 Understanding / Decomposition Agents
    3. 記錄對話歷史
    """

    @staticmethod
    def get_or_create_session(student_id: str, problem_id: str) -> Dict[str, Any]:
        """
        取得或建立學生的 Pre-Coding Logic 會話。
        
        Returns:
            Dict containing:
                - status: 'new' or 'existing'
                - current_stage: 'UNDERSTANDING', 'DECOMPOSITION', or 'COMPLETED'
                - current_score: 1-4
                - chat_log: List of messages
                - opening_message: (if new) Agent's opening question
        """
        with engine.connect() as conn:
            # Check existing status
            status_stmt = select(precoding_logic_status_table).where(
                and_(
                    precoding_logic_status_table.c.student_id == student_id,
                    precoding_logic_status_table.c.problem_id == problem_id
                )
            )
            status_row = conn.execute(status_stmt).fetchone()
            
            # Check existing logs
            logs_stmt = select(precoding_logic_logs_table).where(
                and_(
                    precoding_logic_logs_table.c.student_id == student_id,
                    precoding_logic_logs_table.c.problem_id == problem_id
                )
            )
            logs_row = conn.execute(logs_stmt).fetchone()
            
            if status_row:
                # Existing session
                status_data = status_row._mapping if hasattr(status_row, "_mapping") else status_row
                logs_data = logs_row._mapping if hasattr(logs_row, "_mapping") else logs_row
                chat_log = logs_data["chat_log"] if logs_data else []
                
                # 從 chat_log 最後一則 agent 訊息取得 suggested_replies
                suggested_replies = []
                for msg in reversed(chat_log):
                    if msg.get("role") == "agent":
                        suggested_replies = msg.get("suggested_replies", [])
                        break
                
                return {
                    "status": "existing",
                    "current_stage": status_data["current_stage"],
                    "current_score": status_data["current_score"],
                    "is_completed": status_data["is_completed"],
                    "chat_log": chat_log,
                    "suggested_replies": suggested_replies  # 新增：回傳建議回覆
                }
            
            # Create new session
            problem_info = get_problem_by_id(problem_id) or {}
            opening_msg, opening_suggestions = generate_opening_question(problem_info)
            
            now = datetime.now(timezone.utc)
            initial_log = [{
                "role": "agent",
                "content": opening_msg,
                "stage": "UNDERSTANDING",
                "score": 1,
                "timestamp": now.isoformat(),
                "suggested_replies": opening_suggestions  # 儲存建議回覆
            }]
            
            # Insert status record
            conn.execute(insert(precoding_logic_status_table).values(
                student_id=student_id,
                problem_id=problem_id,
                current_stage="UNDERSTANDING",
                current_score=1,
                is_completed=False
            ))
            
            # Insert logs record
            conn.execute(insert(precoding_logic_logs_table).values(
                student_id=student_id,
                problem_id=problem_id,
                chat_log=initial_log
            ))
            
            conn.commit()
            
            return {
                "status": "new",
                "current_stage": "UNDERSTANDING",
                "current_score": 1,
                "is_completed": False,
                "chat_log": initial_log,
                "opening_message": opening_msg
            }

    @staticmethod
    async def process_chat(
        student_id: str, 
        problem_id: str, 
        message: str
    ) -> Dict[str, Any]:
        """
        處理學生的聊天訊息。
        
        Args:
            student_id: 學生 ID
            problem_id: 題目 ID
            message: 學生輸入的訊息
            
        Returns:
            Dict containing:
                - reply: Agent 的回覆
                - current_stage: 目前階段
                - current_score: 目前分數
                - is_completed: 是否完成
                - chat_log: 更新後的對話紀錄
        """
        # Get current session state
        session = PreCodingManager.get_or_create_session(student_id, problem_id)
        current_stage = session["current_stage"]
        current_score = session["current_score"]
        chat_log = session["chat_log"]
        
        # If already completed, return status
        if session.get("is_completed"):
            return {
                "reply": "您已完成觀念建構階段！可以繼續進行程式碼解釋。",
                "current_stage": "COMPLETED",
                "current_score": 4,
                "is_completed": True,
                "chat_log": chat_log
            }
        
        # Get problem context
        problem_info = get_problem_by_id(problem_id) or {}
        
        # --- 輸入驗證：無效輸入不記錄到 DB，但前端仍顯示 ---
        is_valid, reason = await InputFilterAgent.check(message)
        if not is_valid:
            # 建立臨時 chat_log（僅供前端顯示，不寫入 DB）
            now = datetime.now(timezone.utc)
            temp_chat_log = list(chat_log)  # 複製一份，不影響原始資料
            temp_chat_log.append({
                "role": "student",
                "content": message,
                "stage": current_stage,
                "score": current_score,
                "timestamp": now.isoformat()
            })
            temp_chat_log.append({
                "role": "agent",
                "content": reason,
                "stage": current_stage,
                "score": current_score,
                "timestamp": now.isoformat(),
                "suggested_replies": []
            })
            # 不更新 DB，直接回傳含臨時訊息的 chat_log
            return {
                "reply": reason,
                "current_stage": current_stage,
                "current_score": current_score,
                "is_completed": False,
                "chat_log": temp_chat_log,
                "suggested_replies": []
            }
        # --- 驗證通過，正常流程 ---
        
        # Append student message to log
        now = datetime.now(timezone.utc)
        chat_log.append({
            "role": "student",
            "content": message,
            "stage": current_stage,
            "score": current_score,
            "timestamp": now.isoformat()
        })
        
        # Process based on current stage
        new_stage = current_stage
        new_score = current_score
        is_completed = False
        agent_reply = ""
        
        if current_stage == "UNDERSTANDING":
            reply, score, should_transition, has_decomposition, suggested_replies = await UnderstandingAgent.evaluate(
                chat_log, problem_info
            )
            agent_reply = reply
            new_score = max(current_score, score)  # Score can only go up
            
            if should_transition:
                # Check if we can skip Decomposition
                if has_decomposition:
                    skip = await DecompositionAgent.check_skip_condition(chat_log, problem_info)
                    if skip:
                        new_stage = "COMPLETED"
                        is_completed = True
                        # agent_reply = "太棒了！您已經完整理解題目並列出了解題步驟。觀念建構完成！\n\n🎉 您可以繼續進行程式碼解釋階段了。"
                    else:
                        new_stage = "DECOMPOSITION"
                        # agent_reply = f"{reply}\n\n✅ 理解階段完成！接下來，請試著列出解決這題需要的步驟。"
                else:
                    new_stage = "DECOMPOSITION"
                    # agent_reply = f"{reply}\n\n✅ 理解階段完成！接下來，請試著列出解決這題需要的步驟。"
                # Reset score for new stage
                if new_stage == "DECOMPOSITION":
                    new_score = 1
                    
        elif current_stage == "DECOMPOSITION":
            reply, score, is_stage_complete, suggested_replies = await DecompositionAgent.evaluate(
                chat_log, problem_info
            )
            agent_reply = reply
            new_score = max(current_score, score)
            
            if is_stage_complete:
                new_stage = "COMPLETED"
                is_completed = True
                # agent_reply = "太棒了！您已經完成問題拆解。觀念建構完成！\n\n🎉 您可以繼續進行程式碼解釋階段了。"
                suggested_replies = []  # Clear suggestions on completion
        else:
            suggested_replies = []
        
        # Append agent reply to log (含建議回覆)
        chat_log.append({
            "role": "agent",
            "content": agent_reply,
            "stage": new_stage,
            "score": new_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "suggested_replies": suggested_replies  # 與 agent 訊息一起儲存
        })
        
        # Update database
        with engine.begin() as conn:
            # Update status
            conn.execute(
                update(precoding_logic_status_table).where(
                    and_(
                        precoding_logic_status_table.c.student_id == student_id,
                        precoding_logic_status_table.c.problem_id == problem_id
                    )
                ).values(
                    current_stage=new_stage,
                    current_score=new_score,
                    is_completed=is_completed
                )
            )
            
            # Update logs
            conn.execute(
                update(precoding_logic_logs_table).where(
                    and_(
                        precoding_logic_logs_table.c.student_id == student_id,
                        precoding_logic_logs_table.c.problem_id == problem_id
                    )
                ).values(
                    chat_log=chat_log
                )
            )
            
            if is_completed:
                # Check if legacy record exists
                legacy_stmt = select(precoding_student_answers_table).where(
                    and_(
                        precoding_student_answers_table.c.student_id == student_id,
                        precoding_student_answers_table.c.problem_id == problem_id
                    )
                )
                legacy_row = conn.execute(legacy_stmt).fetchone()
                
                if legacy_row:
                    # Update existing record
                    conn.execute(
                        update(precoding_student_answers_table).where(
                            and_(
                                precoding_student_answers_table.c.student_id == student_id,
                                precoding_student_answers_table.c.problem_id == problem_id
                            )
                        ).values(
                            progress_stage="explain_code"
                        )
                    )
                else:
                    # Insert new record
                    conn.execute(
                        insert(precoding_student_answers_table).values(
                            student_id=student_id,
                            problem_id=problem_id,
                            progress_stage="explain_code",
                            logic_responses=[],
                            error_responses=[],
                            explain_responses=[]
                        )
                    )
        
        return {
            "reply": agent_reply,
            "current_stage": new_stage,
            "current_score": new_score,
            "is_completed": is_completed,
            "chat_log": chat_log,
            "suggested_replies": suggested_replies  # New field for frontend hint buttons
        }

    @staticmethod
    def get_chat_status(student_id: str, problem_id: str) -> Dict[str, Any]:
        """
        取得學生的 Pre-Coding Logic 狀態（不建立新會話）。
        用於前端查詢狀態。
        """
        with engine.connect() as conn:
            status_stmt = select(precoding_logic_status_table).where(
                and_(
                    precoding_logic_status_table.c.student_id == student_id,
                    precoding_logic_status_table.c.problem_id == problem_id
                )
            )
            status_row = conn.execute(status_stmt).fetchone()
            
            if not status_row:
                return {
                    "exists": False,
                    "current_stage": None,
                    "current_score": 0,
                    "is_completed": False,
                    "chat_log": []
                }
            
            status_data = status_row._mapping
            
            logs_stmt = select(precoding_logic_logs_table).where(
                and_(
                    precoding_logic_logs_table.c.student_id == student_id,
                    precoding_logic_logs_table.c.problem_id == problem_id
                )
            )
            logs_row = conn.execute(logs_stmt).fetchone()
            logs_data = logs_row._mapping if logs_row else {}
            chat_log = logs_data.get("chat_log", [])
            
            # 從 chat_log 最後一則 agent 訊息取得 suggested_replies
            suggested_replies = []
            for msg in reversed(chat_log):
                if msg.get("role") == "agent":
                    suggested_replies = msg.get("suggested_replies", [])
                    break
            
            return {
                "exists": True,
                "current_stage": status_data["current_stage"],
                "current_score": status_data["current_score"],
                "is_completed": status_data["is_completed"],
                "chat_log": chat_log,
                "suggested_replies": suggested_replies  # 新增：回傳建議回覆
            }
