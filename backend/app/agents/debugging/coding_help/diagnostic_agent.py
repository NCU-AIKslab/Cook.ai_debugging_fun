"""
Diagnostic Agent 模組
功能：
1. 錯誤報告生成 Agent：分析當前錯誤程式碼生成錯誤報告
2. ZPD Level 判斷 Agent：根據歷史 evidence_report 判斷 ZPD 等級
"""
import os
import json
import logging
from typing import TypedDict, List, Dict, Any
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 初始化 LLM
llm = ChatOpenAI(model="gpt-5.1", temperature=0.3)


class ErrorReport(BaseModel):
    """錯誤報告結構"""
    error_type: str = Field(description="錯誤類型: Syntax/Logic/Runtime")
    location: str = Field(description="錯誤位置：行號或區塊")
    misconception: str = Field(description="學生誤解的觀念 (繁體中文)")
    severity: str = Field(description="嚴重程度: High/Medium/Low")
    error_code: str = Field(description="觸發錯誤的程式碼片段")


class ZPDResult(BaseModel):
    """ZPD 判斷結果"""
    zpd_level: int = Field(description="ZPD 等級: 1 (最具體) ~ 3 (最抽象)")
    reasoning: str = Field(description="判斷理由")


async def generate_error_report(
    current_code: str,
    error_message: str,
    problem_info: Dict[str, str]
) -> Dict[str, Any]:
    """
    生成單次錯誤報告
    
    Args:
        current_code: 學生目前的程式碼
        error_message: 錯誤訊息
        problem_info: 題目資訊
        
    Returns:
        包含錯誤分析的報告 (dict)
    """
    prompt = f"""
    你是一位專業的 Python 教學助理。請分析學生的錯誤並輸出 JSON。
    
    程式題目: {json.dumps(problem_info, ensure_ascii=False)}
    學生程式碼: 
    ```python
    {current_code}
    ```
    程式碼錯誤訊息: {error_message}

    格式規範:
    {{
        "error_type": "Syntax (語法錯誤) / Logic (邏輯錯誤) / Runtime (執行錯誤)",
        "location": "行號或區塊",
        "misconception": "詳細解釋學生誤解的觀念 (繁體中文)",
        "severity": "High/Medium/Low",
        "error_code": "觸發錯誤的程式碼片段"
    }}
    """
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content="你是程式碼分析專家。請只輸出 JSON，不要有其他文字。"),
            HumanMessage(content=prompt)
        ])
        
        content = response.content.replace("```json", "").replace("```", "").strip()
        report = json.loads(content)
        
        # 確保錯誤程式碼欄位存在
        if "error_code" not in report:
            report["error_code"] = current_code
            
        return report
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return {
            "error_type": "Unknown",
            "location": "Unknown",
            "misconception": "解析失敗",
            "severity": "Medium",
            "error_code": current_code
        }
    except Exception as e:
        logger.error(f"Error report generation failed: {e}")
        return {
            "error_type": "Unknown",
            "location": "Unknown",
            "misconception": str(e),
            "severity": "Medium",
            "error_code": current_code
        }


async def determine_zpd_level(
    previous_reports: List[Dict],
    current_report: Dict[str, Any]
) -> Dict[str, Any]:
    """
    根據歷史 evidence_report 判斷 ZPD Level
    
    Args:
        previous_reports: 歷史錯誤報告列表
        current_report: 當前錯誤報告
        
    Returns:
        包含 zpd_level 和 reasoning 的結果
    """
    # 統計錯誤類型重複次數
    current_error_type = current_report.get("error_type", "")
    current_misconception = current_report.get("misconception", "")
    
    # 建構歷史分析摘要
    history_summary = []
    for i, report in enumerate(previous_reports, 1):
        history_summary.append(f"第 {i} 次錯誤: {report.get('error_type', 'Unknown')} - {report.get('misconception', 'N/A')}")
    
    history_text = "\n".join(history_summary) if history_summary else "無歷史錯誤記錄"
    
    prompt = f"""
    你是一位教育心理學專家，專精於 Vygotsky 的近側發展區 (ZPD) 理論。
    請根據學生的錯誤歷史，判斷目前應該給予的教學引導強度。
    
    【歷史錯誤記錄】
    {history_text}
    
    【當前錯誤】
    類型: {current_error_type}
    誤解: {current_misconception}
    
    【ZPD 等級定義】
    - Level 1: 學生重複犯相同類型錯誤 (>=2次)，需要最具體的引導，可提供部分範例
    - Level 2: 學生對此類型錯誤有 1 次歷史記錄，給予具體提示但不要給答案
    - Level 3: 首次出現此類型錯誤，僅給予方向性提示讓學生自行思考
    
    請輸出 JSON:
    {{
        "zpd_level": 1-3 的整數,
        "reasoning": "判斷理由"
    }}
    """
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content="你是教育心理學專家。請只輸出 JSON。"),
            HumanMessage(content=prompt)
        ])
        
        content = response.content.replace("```json", "").replace("```", "").strip()
        result = json.loads(content)
        
        # 確保 zpd_level 在有效範圍
        zpd_level = result.get("zpd_level", 3)
        if not isinstance(zpd_level, int) or zpd_level < 1 or zpd_level > 3:
            zpd_level = 3
            
        return {
            "zpd_level": zpd_level,
            "reasoning": result.get("reasoning", "")
        }
        
    except Exception as e:
        logger.error(f"ZPD determination failed: {e}")
        
        # Fallback: 簡單規則判斷
        repeat_count = sum(
            1 for rep in previous_reports 
            if rep.get("error_type") == current_error_type
        )
        
        if repeat_count >= 2:
            zpd_level = 1
        elif repeat_count == 1:
            zpd_level = 2
        else:
            zpd_level = 3
            
        return {
            "zpd_level": zpd_level,
            "reasoning": f"基於規則判斷：相同錯誤類型出現 {repeat_count} 次"
        }


async def run_diagnostic(
    current_code: str,
    error_message: str,
    problem_info: Dict[str, str],
    previous_reports: List[Dict]
) -> Dict[str, Any]:
    """
    執行完整診斷流程
    
    Returns:
        包含 evidence_report 和 zpd_level 的完整診斷結果
    """
    # Step 1: 生成錯誤報告
    error_report = await generate_error_report(current_code, error_message, problem_info)
    
    # Step 2: 判斷 ZPD Level
    zpd_result = await determine_zpd_level(previous_reports, error_report)
    
    return {
        "evidence_report": error_report,
        "zpd_level": zpd_result["zpd_level"],
        "zpd_reasoning": zpd_result["reasoning"]
    }
