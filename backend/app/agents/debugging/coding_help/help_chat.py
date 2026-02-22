"""
Help Chat 模組
功能：
1. Input Guard Agent：阻擋無效輸入 (亂數、惡意程式碼、過長內容)
2. Chat Response：依據 ZPD Level、evidence_report 與對話紀錄生成回覆
"""
import os
import json
import re
import logging
from typing import List, Dict, Any
from datetime import datetime

import tiktoken
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from backend.app.agents.debugging.db import save_llm_charge

from .scaffolding_agent import generate_scaffold_response

logger = logging.getLogger(__name__)

# 初始化 LLM
llm = ChatOpenAI(model="gpt-5.1", temperature=0.3)
llm2 = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
# 常數定義
MAX_TOKEN_LIMIT = 350

def count_tokens(text: str) -> int:
    """計算 Token 數量"""
    try:
        encoding = tiktoken.encoding_for_model("gpt-4")
        return len(encoding.encode(text))
    except Exception:
        return len(text)


class InputValidation(BaseModel):
    """輸入驗證結果"""
    is_valid: bool = Field(description="是否為有效輸入")
    reason: str = Field(description="驗證理由")
    sanitized_input: str = Field(description="清理後的輸入 (若無效則為空)")


def clean_markdown_filter(text: str) -> str:
    """去除字串中的 Markdown 標記語法"""
    if not text:
        return ""
    # 去除粗體符號但保留文字內容
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    # 去除標題符號
    text = re.sub(r'#+\s?', '', text)
    return text.strip()


async def validate_input(
    message: str,
    student_id: str = None,
    problem_id: str = None,
) -> Dict[str, Any]:
    """
    Input Guard Agent：驗證使用者輸入
    
    Args:
        message: 使用者輸入的訊息
        
    Returns:
        驗證結果 dict
    """
    # 1. Token 長度檢查
    if count_tokens(message) > MAX_TOKEN_LIMIT:
        return {
            "is_valid": False,
            "reason": f"訊息過長 (超過 {MAX_TOKEN_LIMIT} Tokens，約 300 中文字或 300 英文單字)，請嘗試精簡描述。",
            "sanitized_input": ""
        }
    
    # 2. 空白或僅空格檢查
    if not message or not message.strip():
        return {
            "is_valid": False,
            "reason": "請輸入有效的問題。",
            "sanitized_input": ""
        }
    
    # 3. 純亂數/亂碼檢查 (使用簡單規則)
    cleaned = message.strip()
    
    # 檢查是否只有數字和符號
    if re.match(r'^[\d\s\.\,\!\?\@\#\$\%\^\&\*\(\)\-\_\+\=\[\]\{\}\|\\\;\:\'\"\<\>\,\.\/\~\`]+$', cleaned):
        return {
            "is_valid": False,
            "reason": "請輸入有意義的問題，不要只輸入亂碼或符號。",
            "sanitized_input": ""
        }
    return  {
            "is_valid": True,
            "reason": "",
            "sanitized_input": cleaned
        }
    # # 4. 使用 LLM 進行更深層的驗證
    # prompt = f"""
    # 你是輸入驗證專家。你只輸出 JSON。判斷輸入是否有效。
    #     【無效輸入類型】
    #     - 無效輸入：
    #     1. 亂打的字元/鍵盤亂按 (如: "asdfghjkl", "!@#$%")
    #     2. 空白或只有標點符號

    
    #     請輸出 JSON:
    #     {{
    #         "is_valid": true/false,
    #         "reason": "判斷理由"
    #     }}
    # """
    
    # try:
    #     response = await llm2.ainvoke([
    #         SystemMessage(content=prompt),
    #         HumanMessage(content=cleaned)
    #     ])
        
    #     content = response.content.replace("```json", "").replace("```", "").strip()
    #     result = json.loads(content)
    #     # 記錄 token 用量
    #     if student_id:
    #         usage = response.response_metadata.get("token_usage", {})
    #         details = usage.get("prompt_tokens_details") or {}
    #         save_llm_charge(
    #             student_id=student_id,
    #             usage_type="code_correction",
    #             model_name="gpt-4o-mini",
    #             input_tokens=usage.get("prompt_tokens", 0),
    #             cached_input_tokens=details.get("cached_tokens", 0),
    #             output_tokens=usage.get("completion_tokens", 0),
    #             problem_id=problem_id,
    #         )
    #     return {
    #         "is_valid": result.get("is_valid", True),
    #         "reason": result.get("reason", ""),
    #         "sanitized_input": cleaned if result.get("is_valid", True) else ""
    #     }
        
    # except Exception as e:
    #     logger.error(f"Input validation LLM error: {e}")
    #     # Fallback: 如果 LLM 驗證失敗，允許通過
    #     return {
    #         "is_valid": True,
    #         "reason": "LLM 驗證跳過",
    #         "sanitized_input": cleaned
    #     }


async def generate_chat_response(
    message: str,
    zpd_level: int,
    evidence_report: Dict[str, Any],
    problem_info: Dict[str, str],
    chat_log: List[Dict[str, Any]],
    student_id: str = None,
    problem_id: str = None,
) -> str:
    """
    依據 ZPD Level、evidence_report 與對話紀錄生成回覆
    
    Args:
        message: 使用者當前訊息
        zpd_level: ZPD 等級
        evidence_report: 當前錯誤報告
        problem_info: 題目資訊
        chat_log: 對話紀錄
        
    Returns:
        AI 回覆文字
    """
    # 根據 ZPD 等級決定教學策略
    strategies = {
        1: "引導學生思考修正邏輯，可提供部分範例。",
        2: "給予具體提示。",
        3: "僅給予方向性提示。"
    }
    strategy = strategies.get(zpd_level, strategies.get(3))
    
    problem_context = f"題目: {problem_info.get('title', '')}\n描述: {problem_info.get('description', '')}"
    
    # 建構對話歷史
    messages = [
        SystemMessage(content=f"""
        你是一位程式設計輔導老師，請根據對話紀錄和學生現在提問，提供適當的引導。

        題目資訊：{problem_context}
        **注意**：輸出格式需參考 samples
        學生錯誤程式碼診斷結果：{json.dumps(evidence_report, ensure_ascii=False)}
        
        【教學策略 (ZPD 等級 {zpd_level})】: {strategy}

        請遵守：
        1. 使用繁體中文，**簡單明瞭字數100字內**，條列式回覆，不帶任何情緒。
        2. 嚴禁使用 Markdown 語法。
        3. 依照策略強度提供引導，不要直接給出完整正確答案。
        4. **不可回答與題目無相關問題**
        """)
    ]
    
    # 從 chat_log 建構對話歷史 (取最近 4 則)
    recent_chat = chat_log[-4:] if len(chat_log) > 4 else chat_log
    for entry in recent_chat:
        role = entry.get("role", "")
        content = entry.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "agent":
            messages.append(AIMessage(content=content))
    
    # 加入當前使用者訊息
    messages.append(HumanMessage(content=message))
    
    try:
        response = await llm.ainvoke(messages)
        # 記錄 token 用量
        if student_id:
            usage = response.response_metadata.get("token_usage", {})
            details = usage.get("prompt_tokens_details") or {}
            save_llm_charge(
                student_id=student_id,
                usage_type="code_correction",
                model_name="gpt-5.1",
                input_tokens=usage.get("prompt_tokens", 0),
                cached_input_tokens=details.get("cached_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                problem_id=problem_id,
            )
        return clean_markdown_filter(response.content)
        
    except Exception as e:
        logger.error(f"Chat response generation failed: {e}")
        return "系統暫時無法回應，請稍後再試。"


async def process_chat(
    message: str,
    zpd_level: int,
    evidence_report: Dict[str, Any],
    problem_info: Dict[str, str],
    chat_log: List[Dict[str, Any]],
    student_id: str = None,
    problem_id: str = None,
) -> Dict[str, Any]:
    """
    處理聊天請求的主要流程
    
    Returns:
        包含 response, is_valid, updated_chat_log 的結果
    """
    # Step 1: 輸入驗證
    validation = await validate_input(message, student_id=student_id, problem_id=problem_id)
    
    if not validation["is_valid"]:
        return {
            "is_valid": False,
            "response": validation["reason"],
            "updated_chat_log": chat_log  # 不更新對話紀錄
        }
    
    # Step 2: 生成回覆
    response = await generate_chat_response(
        message=message,
        zpd_level=zpd_level,
        evidence_report=evidence_report,
        problem_info=problem_info,
        chat_log=chat_log,
        student_id=student_id,
        problem_id=problem_id,
    )
    
    # Step 3: 更新對話紀錄
    timestamp = datetime.now().isoformat()
    updated_chat_log = chat_log.copy()
    updated_chat_log.append({
        "role": "user",
        "content": message,
        "zpd": zpd_level,
        "timestamp": timestamp
    })
    updated_chat_log.append({
        "role": "agent",
        "content": response,
        "zpd": zpd_level,
        "timestamp": timestamp
    })
    
    return {
        "is_valid": True,
        "response": response,
        "updated_chat_log": updated_chat_log
    }
