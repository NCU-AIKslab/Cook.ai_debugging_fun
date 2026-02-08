"""
Pre-Coding Agents Module
"""

import os
import json
from typing import Dict, Any, List, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-5.1", 
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY")
)

# --- 1. 共用輔助 Agent ---

class InputFilterAgent:
    """
    負責過濾學生輸入的 Agent。
    """
    @staticmethod
    async def check(student_input: str) -> bool:
        """
        檢查輸入有效性。只回傳 True/False，後續回應邏輯交由主流程控制。
        """
        system_prompt = """你是一個對話過濾器。請判斷學生的輸入是否為「無意義內容」或「惡意亂碼」。

【判斷標準】
- 有效輸入：與程式、邏輯、數學相關，或是表示不知道、請求協助、簡單的問候 (如 "嗨", "你好")。
- 無效輸入：
  1. 亂打的鍵盤符號 (如 "asdf", ".....", "123123")
  2. 完全無法理解的亂碼
  3. 顯著的惡意攻擊或髒話
  4. 空白或只有標點符號

請以 JSON 回覆：
{
    "is_valid": true/false
}
"""
        try:
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"學生輸入: {student_input}")
            ])
            result = json.loads(response.content)
            return result.get("is_valid", True)
        except Exception:
            return True


class SuggestionAgent:
    """
    負責生成「學生視角」的建議回覆選項。
    需分析「全部歷史紀錄」來決定給予什麼難度的選項。
    """
    @staticmethod
    async def generate(
        agent_last_question: str,
        chat_history: List[Dict[str, Any]],
        problem_context: Dict[str, Any]
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
        problem_context: Dict[str, Any]
    ) -> Tuple[str, int, bool, bool, List[str]]:
        
        # 1. 提取最新學生輸入
        last_student_msg = next((msg['content'] for msg in reversed(chat_history) if msg['role'] == 'student'), "")
        
        # 2. 尋找 Agent 上一次的發言 (用於無效輸入時的 Context)
        last_agent_msg = next((msg['content'] for msg in reversed(chat_history) if msg['role'] == 'agent'), "請說明這題的輸入與輸出是什麼？")

        # --- 無效輸入處理邏輯 ---
        if last_student_msg:
            is_valid = await InputFilterAgent.check(last_student_msg)
            
            if not is_valid:
                # 若無效：
                # 1. 取得針對「上一個問題」的建議回覆 (傳入完整歷史供分析)
                suggested_replies = await SuggestionAgent.generate(last_agent_msg, chat_history, problem_context)
                
                # 2. 組合回覆訊息：警告 + 重述問題
                reply_msg = f"無效輸入請再次作答。\n\n(系統提示：{last_agent_msg})"
                
                # 3. 回傳 (分數維持 1 或維持現狀，不推進階段)
                return reply_msg, 1, False, False, suggested_replies
        # -----------------------

        # 3. 準備 Prompt 資料 (有效輸入才進入這裡)
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
            
            result = json.loads(response.content)
            
            agent_reply = result.get("reply", "請試著描述這題的輸入是什麼？")
            score = min(4, max(1, int(result.get("score", 1))))
            has_decomposition = result.get("has_decomposition", False)
            should_transition = score >= 4
            
            # 5. 針對「Agent 這次產生的新回覆」生成建議選項
            suggested_replies = await SuggestionAgent.generate(agent_reply, chat_history, problem_context)
            
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
        problem_context: Dict[str, Any]
    ) -> Tuple[str, int, bool, List[str]]:
        
        # 1. 提取最新學生輸入
        last_student_msg = next((msg['content'] for msg in reversed(chat_history) if msg['role'] == 'student'), "")
        
        # 2. 尋找 Agent 上一次的發言
        last_agent_msg = next((msg['content'] for msg in reversed(chat_history) if msg['role'] == 'agent'), "請試著列出解題步驟。")
        
        # --- 無效輸入處理邏輯 ---
        if last_student_msg:
            is_valid = await InputFilterAgent.check(last_student_msg)
            if not is_valid:
                # 重新針對上一個問題生成建議
                suggested_replies = await SuggestionAgent.generate(last_agent_msg, chat_history, problem_context)
                
                reply_msg = f"無效輸入請再次作答。\n\n(系統提示：{last_agent_msg})"
                
                return reply_msg, 1, False, suggested_replies
        # -----------------------

        # 3. 準備 Prompt 資料
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
3. 如果學生還沒完全拆解，用引導性問題幫助他們列出步驟
4. 若學生在同一個點卡住 2 次以上，提供選擇題式的提示答案(不要以疑問句方式呈現)

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
            
            result = json.loads(response.content)
            
            agent_reply = result.get("reply", "請試著列出解決這題需要的步驟")
            score = min(4, max(1, int(result.get("score", 1))))
            is_complete = score >= 4
            
            # 5. 針對新回覆生成建議
            suggested_replies = await SuggestionAgent.generate(agent_reply, chat_history, problem_context)
            
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