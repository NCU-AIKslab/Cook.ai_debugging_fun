"""
Pre-Coding Agents Module
"""

import os
import json
from typing import Dict, Any, List, Tuple, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

import tiktoken
from backend.app.agents.debugging.db import save_llm_charge

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-5.1", 
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY")
)
llm2 = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=os.getenv("OPENAI_API_KEY"))

MAX_INTENTION_TOKEN_LIMIT = 350

def count_tokens(text: str) -> int:
    """計算 Token 數量"""
    try:
        encoding = tiktoken.encoding_for_model("gpt-4")
        return len(encoding.encode(text))
    except Exception:
        # Fallback approximation: 1 token ~= 1.5 chars for mixed, but safe side 1 char
        return len(text)

# --- 1. 共用輔助 Agent ---

# --- 1. 共用輔助 Agent ---

class InputFilterAgent:
    """
    負責過濾學生輸入的 Agent。
    """
    @staticmethod
    async def check(student_input: str, student_id: str = None, problem_id: str = None) -> Tuple[bool, str]:
        """
        檢查輸入有效性。
        Returns:
            (is_valid, reason)
        """
        # 1. Check Token Limit
        if count_tokens(student_input) > MAX_INTENTION_TOKEN_LIMIT:
            return False, f"您的輸入過長 (超過 {MAX_INTENTION_TOKEN_LIMIT} Tokens，約 300 中文字)，請嘗試精簡描述。"

        system_prompt = f"""你是輸入驗證專家。你只輸出 JSON。判斷輸入是否有效。
        【無效輸入類型】
        - 無效輸入：
        1. 亂打的字元/鍵盤亂按 (如: "asdfghjkl", "!@#$%")
        2. 空白或只有標點符號

        注意：
        - 使用者描述問題、回報 bug、詢問系統行為，不算一般閒聊，應判為有效。
        - 單一數字（包含 0）可能是合法答案，不能因為短就判無效。
    
        請輸出 JSON:
        {{
            "is_valid": true/false,
            "reason": "判斷理由"
        }}
        """
        try:
            response = await llm2.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=student_input)
            ])
            # 記錄 token 用量
            if student_id:
                usage = response.response_metadata.get("token_usage", {})
                details = usage.get("prompt_tokens_details") or {}
                save_llm_charge(
                    student_id=student_id,
                    usage_type="intention",
                    model_name="gpt-4o",
                    input_tokens=usage.get("prompt_tokens", 0),
                    cached_input_tokens=details.get("cached_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    problem_id=problem_id,
                )
            result = json.loads(response.content)
            is_valid = result.get("is_valid", True)
            reason = result.get("reason", "輸入無效，請重新輸入。")
            return is_valid, reason
        except Exception:
            return True, ""


class SuggestionAgent:
    """
    負責生成「學生視角」的建議回覆選項。
    需分析「全部歷史紀錄」來決定給予什麼難度的選項。
    """
    @staticmethod
    async def generate(
        agent_last_question: str,
        chat_history: List[Dict[str, Any]],
        problem_context: Dict[str, Any],
        student_id: str = None,
        problem_id: str = None,
    ) -> List[str]:
        
        # 1. 整理歷史紀錄為文本
        history_text = "\n".join([
            f"{'學生' if msg['role'] == 'student' else 'Agent'}: {msg['content']}"
            for msg in chat_history[-10:] # 取最近 10 則以免 context 太長
        ])

        problem_info = f"題目: {problem_context.get('title', '')}"
        
        system_prompt = f"""你是一位程式設計教學助教，正在引導學生**理解程式題目**與**拆解題目**。
請分析「對話歷史」中學生的程度與狀態，針對「Agent 剛剛問的問題」，提供 1~3 個「學生可能的回覆選項」。

【題目資訊】
{problem_info}

【對話歷史 (分析學生狀態)】
{history_text}

【Agent 剛剛問的問題】
{agent_last_question}


【你的任務】
1. 分析學生目前的回答，判斷他們對題目的理解程度
2. 以學生回覆視角生成回覆選項

【重要規則】
- 使用繁體中文生成選項
- 回覆簡潔明瞭，不超過 15 字
- 不要包含多餘的標點符號
- 不要包含多餘的空行
- 選項內容不要重複
- 內容須正確

請以 JSON 回覆：
{{
    "options": ["選項1", "選項2", "選項3"]
}}
"""
        try:
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content="請根據學生歷史狀態與當前問題，生成建議回答")
            ])
            # 記錄 token 用量
            if student_id:
                usage = response.response_metadata.get("token_usage", {})
                details = usage.get("prompt_tokens_details") or {}
                save_llm_charge(
                    student_id=student_id,
                    usage_type="intention",
                    model_name="gpt-5.1",
                    input_tokens=usage.get("prompt_tokens", 0),
                    cached_input_tokens=details.get("cached_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    problem_id=problem_id,
                )
            result = json.loads(response.content)
            return result.get("options", [])
        except Exception:
            return ["我不太確定，可以給個提示嗎？", "這題的輸入是...", "需要更多說明"]


# --- 2. 主要流程 Agent ---

class UnderstandingAgent:
    """
    負責「問題理解」階段的 Agent。
    """
    
    RUBRIC = """
    評分標準 (1-4 分):
    1 分: 無法設定解題目標，且無法識別問題限制 
    2 分: 能夠設定解題目標，但無法識別問題限制
    3 分: 能夠設定解題目標，且能夠識別問題限制
    4 分: 能夠設定解題目標、識別問題限制，並能識別與問題相關的知識或資訊
    """

    @staticmethod
    async def evaluate(
        chat_history: List[Dict[str, Any]],
        problem_context: Dict[str, Any],
        student_id: str = None,
        problem_id: str = None,
    ) -> Tuple[str, int, bool, bool, List[str]]:
        
        # 1. 提取最新學生輸入
        last_student_msg = next((msg['content'] for msg in reversed(chat_history) if msg['role'] == 'student'), "")
        
        # 2. 尋找 Agent 上一次的發言 (用於無效輸入時的 Context)
        last_agent_msg = next((msg['content'] for msg in reversed(chat_history) if msg['role'] == 'agent'), "請說明這題的輸入與輸出是什麼？")

        # 3. 準備 Prompt 資料 (輸入驗證已在 manager.py 中完成)
        history_text = "\n".join([
            f"{'學生' if msg['role'] == 'student' else 'Agent'}: {msg['content']}"
            for msg in chat_history if msg.get('content')
        ])
        
        problem_text = f"""
題目標題: {problem_context.get('title', '')}
題目描述: {problem_context.get('description', '')}
輸入說明: {problem_context.get('input_description', '')}
輸出說明: {problem_context.get('output_description', '')}
"""

        system_prompt = f"""你是一位程式設計教學助教，正在引導學生理解程式題目。

【題目資訊】
{problem_text}

【評分標準】
{UnderstandingAgent.RUBRIC}

【對話歷史】
{history_text}

【你的任務】
1. 分析學生目前的回答，判斷他們對題目的理解程度
2. 給予 1-4 分的評分
3. 如果學生還沒完全理解，用引導性問題幫助他們
4. 如果學生的回答中已經包含了「解題步驟」的描述，請標記 has_decomposition = true

【重要規則】
- 使用繁體中文回覆
- 不要直接給答案，用引導性問題
- 每次回覆簡潔明瞭，不超過 70 字
- 一次最多問兩個問題
- 不要告訴學生目前進度(包括得分以及進度)

請以 JSON 格式回覆:
{{
    "reply": "你對學生的回覆內容",
    "score": 1-4 的評分,
    "has_decomposition": true/false
}}
"""

        try:
            # 4. 執行評估
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content="請根據以上對話歷史進行評估")
            ])
            # 記錄 token 用量
            if student_id:
                usage = response.response_metadata.get("token_usage", {})
                details = usage.get("prompt_tokens_details") or {}
                save_llm_charge(
                    student_id=student_id,
                    usage_type="intention",
                    model_name="gpt-5.1",
                    input_tokens=usage.get("prompt_tokens", 0),
                    cached_input_tokens=details.get("cached_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    problem_id=problem_id,
                )
            
            result = json.loads(response.content)
            
            agent_reply = result.get("reply", "請試著描述這題的輸入是什麼？")
            score = min(4, max(1, int(result.get("score", 1))))
            has_decomposition = result.get("has_decomposition", False)
            should_transition = score >= 4
            
            # 5. 針對「Agent 這次產生的新回覆」生成建議選項
            suggested_replies = await SuggestionAgent.generate(
                agent_reply, chat_history, problem_context,
                student_id=student_id, problem_id=problem_id
            )
            
            return agent_reply, score, should_transition, has_decomposition, suggested_replies
            
        except Exception as e:
            # Fallback
            return "請說說看這題的輸入是什麼？輸出又是什麼？", 1, False, False, ["輸入是整數", "輸出是字串", "我不太確定"]


class DecompositionAgent:
    """
    負責「問題拆解」階段的 Agent。
    """
    
    RUBRIC = """
    評分標準 (1-4 分):
    1 分: 學生尚未提供任何步驟
    2 分: 學生提供了部分步驟，但不完整或邏輯不通
    3 分: 學生提供了合理的步驟，但缺少某些關鍵環節
    4 分: 學生提供了完整、邏輯通順的解題步驟
    """

    @staticmethod
    async def evaluate(
        chat_history: List[Dict[str, Any]],
        problem_context: Dict[str, Any],
        student_id: str = None,
        problem_id: str = None,
    ) -> Tuple[str, int, bool, List[str]]:
        
        # 1. 提取最新學生輸入
        last_student_msg = next((msg['content'] for msg in reversed(chat_history) if msg['role'] == 'student'), "")
        
        # 2. 尋找 Agent 上一次的發言
        last_agent_msg = next((msg['content'] for msg in reversed(chat_history) if msg['role'] == 'agent'), "請試著列出解題步驟。")

        # 3. 準備 Prompt 資料 (輸入驗證已在 manager.py 中完成)
        history_text = "\n".join([
            f"{'學生' if msg['role'] == 'student' else 'Agent'}: {msg['content']}"
            for msg in chat_history if msg.get('content')
        ])
        
        problem_text = f"""
題目標題: {problem_context.get('title', '')}
題目描述: {problem_context.get('description', '')}
輸入說明: {problem_context.get('input_description', '')}
輸出說明: {problem_context.get('output_description', '')}
"""

        system_prompt = f"""你是一位程式設計教學助教，正在引導學生拆解程式題目。

【題目資訊】
{problem_text}

【評分標準】
{DecompositionAgent.RUBRIC}

【對話歷史】
{history_text}

【你的任務】
1. 分析學生目前的回答，判斷他們的拆解程度
2. 給予 1-4 分的評分
3. 如果學生還沒完全拆解(分數1~3分)，用引導性問題幫助他們列出步驟
4. 若分數為 4 分：reply 必須是「肯定結語」，絕對不可以繼續提問
  - 正確範例：「你已完整列出解題步驟，邏輯清楚！觀念建構完成，可以繼續下一階段了。」
5. 若學生在同一個點卡住 2 次以上，提供選擇題式的提示答案(不要以疑問句方式呈現)

【重要規則】
- 使用繁體中文回覆
- 不要直接給答案
- 每次回覆簡潔明瞭，不超過 70 字
- 一次最多問兩個問題
- 不要告訴學生目前進度(包括得分以及進度)
- 盡量避免提及程式語法

請以 JSON 格式回覆:
{{
    "reply": "你對學生的回覆內容",
    "score": 1-4 的評分
}}
"""

        try:
            # 4. 執行評估
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content="請根據以上對話歷史進行評估")
            ])
            # 記錄 token 用量
            if student_id:
                usage = response.response_metadata.get("token_usage", {})
                details = usage.get("prompt_tokens_details") or {}
                save_llm_charge(
                    student_id=student_id,
                    usage_type="intention",
                    model_name="gpt-5.1",
                    input_tokens=usage.get("prompt_tokens", 0),
                    cached_input_tokens=details.get("cached_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    problem_id=problem_id,
                )
            
            result = json.loads(response.content)
            
            agent_reply = result.get("reply", "請試著列出解決這題需要哪些步驟")
            score = min(4, max(1, int(result.get("score", 1))))
            is_complete = score >= 4
            
            # 5. 針對新回覆生成建議
            suggested_replies = await SuggestionAgent.generate(
                agent_reply, chat_history, problem_context,
                student_id=student_id, problem_id=problem_id
            )
            
            return agent_reply, score, is_complete, suggested_replies
            
        except Exception as e:
            return "請試著列出解決這題需要哪些步驟？", 1, False, ["第一步是...", "使用迴圈...", "最後輸出..."]

    # check_skip_condition 維持不變...
    @staticmethod
    async def check_skip_condition(
        chat_history: List[Dict[str, Any]],
        problem_context: Dict[str, Any]
    ) -> bool:
        # (保持原有的代碼)
        return False

def generate_opening_question(problem_context: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    根據題目產生開場問題。
    修正重點：
    1. 針對「解題目標」進行提問，而非輸入輸出。
    2. 初始狀態不給予 Suggestion (hints)，強迫學生思考。
    """
    title = problem_context.get('title', '這題')
    
    # 具體的任務詢問方式
    opening_text = (
        f"請先用你自己的話簡單說明：\n"
        f"這題的主要任務目標是什麼？"
    )
    
    # 需求：一開始不要給予提示
    suggested_replies = []
    
    return opening_text, suggested_replies