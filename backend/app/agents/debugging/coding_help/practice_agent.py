"""
Practice Agent 模組
功能：針對全部歷史 evidence_report 整理錯誤觀念後生成練習選擇題
"""
import os
import json
import logging
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# 初始化 LLM
llm = ChatOpenAI(model="gpt-5.1", temperature=0.3)


async def generate_practice_questions(
    previous_reports: List[Dict],
    problem_info: Dict[str, str],
    current_report: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    根據學生的錯誤歷史生成練習選擇題
    
    Args:
        previous_reports: 歷史錯誤報告列表
        problem_info: 題目資訊
        current_report: 當前錯誤報告 (可選)
        
    Returns:
        練習題列表
    """
    # 彙整所有錯誤觀念
    all_reports = previous_reports.copy() if previous_reports else []
    if current_report:
        all_reports.append(current_report)
    
    if not all_reports:
        logger.warning("No error reports found for practice generation")
        return []
    
    # 整理錯誤觀念摘要
    misconceptions = []
    for i, report in enumerate(all_reports, 1):
        if report:
            misconceptions.append({
                "index": i,
                "error_type": report.get("error_type", "Unknown"),
                "misconception": report.get("misconception", ""),
                "error_code": report.get("error_code", "")
            })
    
    misconceptions_text = json.dumps(misconceptions, ensure_ascii=False, indent=2)
    
    prompt = f"""
    請根據學生之前的錯誤，設計 1 題「單選題」來鞏固觀念。
    
    題目目標: {json.dumps(problem_info, ensure_ascii=False)}
    
    學生錯誤歷史 (請針對最常出現或最關鍵的誤解設計題目):
    {misconceptions_text}
    
    【生成規範】:
    1. 題目敘述請用自然語言，避免直接寫出 Python 語法（例如：不要寫「使用 split()」，改寫「將字串以空格拆分」）。
    2. 需給出**完整程式碼**，並在填空處用 "_____" 表示。
    3. 提供 3 個選項，正確答案隨機分佈。
    4. 每個選項需包含 feedback (回饋)。
    
    格式規範 (JSON Array):
    [
        {{
            "id": "Q1",
            "type": "logic", 
            "question": {{
                "text": "題目描述",
                "code": {{ "content": "```\n<帶有錯誤的完整程式碼>\n```", "language": "python" }}
            }},
            "options": [
                {{ "id": 1, "label": "選項描述...", "feedback": "❌ 錯誤原因..." }},
                {{ "id": 2, "label": "選項描述...", "feedback": "✅ 正確！..." }},
                {{ "id": 3, "label": "選項描述...", "feedback": "❌ 錯誤原因..." }}
            ],
            "answer_config": {{ "correct_id": 2, "explanation": "詳解..." }}
        }}
    ]
    """
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content="你是程式教育專家。請只輸出 JSON Array，不要有其他文字。"),
            HumanMessage(content=prompt)
        ])
        
        content = response.content.replace("```json", "").replace("```", "").strip()
        practice_q = json.loads(content)
        
        if isinstance(practice_q, list):
            return practice_q
        else:
            return [practice_q]
            
    except json.JSONDecodeError as e:
        logger.error(f"Practice question JSON parsing error: {e}")
        return []
    except Exception as e:
        logger.error(f"Practice question generation failed: {e}")
        return []


async def run_practice_generation(
    previous_reports: List[Dict],
    problem_info: Dict[str, str],
    current_report: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    執行練習題生成流程
    
    Returns:
        包含練習題的結果
    """
    practice_questions = await generate_practice_questions(
        previous_reports=previous_reports,
        problem_info=problem_info,
        current_report=current_report
    )
    
    return {
        "practice_question": practice_questions,
        "question_count": len(practice_questions)
    }
