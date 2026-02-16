import os
import json
from typing import List
from pydantic import BaseModel, Field
from openai import OpenAI

# ================= 1. 設定與常數 =================

CONCEPT_DETAILS = {
    'C1': '變數與資料型態: type(), input(), print(), 字串連接(+)。禁止迴圈與判斷式。',
    'C2': '數值與字串運算: +, -, *, /, //, %, **, slicing, index, len(), find(), count()。',
    'C3': 'List列表: append, remove, pop, split, join, sort, index。',
    'C4': '條件判斷: if, elif, else, and, or, not。',
    'C5': 'For迴圈: range, list iteration, break, continue。',
    'C6': 'While迴圈: while, break, continue, 無窮迴圈。',
    'C7': 'Dictionary字典: key-value, get, keys, values。',
    'C8': 'Function函式: def, return, global, 參數。'
}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ================= 2. Pydantic Schema =================

# ================= 2. Pydantic Schema =================

class ArchitectureItem(BaseModel):
    intention: str = Field(..., description="這段程式碼的意圖 (Intention)")
    code: str = Field(..., description="對應的程式碼 (Code)")

class ArchitectureQuestion(BaseModel):
    code: str = Field(..., description="程式碼模板")

# ================= 3. AI 生成邏輯 =================

def get_unit_from_id(problem_id: str) -> str:
    if "_" in problem_id:
        return problem_id.split("_")[0]
    return "C1"

def generate_architecture_questions(problem_data, problem_id, manual_unit=None):
    # Expecting problem_data to have solution_code at the end
    if len(problem_data) == 6:
        title, desc, in_desc, out_desc, samples, solution_code = problem_data
    else:
        # Fallback if no solution code provided (should be handled by caller)
        title, desc, in_desc, out_desc, samples = problem_data[:5]
        solution_code = "# No solution code provided"
        
    main_concept = manual_unit if manual_unit else get_unit_from_id(problem_id)
    allowed_scope = f"- {main_concept}: {CONCEPT_DETAILS.get(main_concept, '')}"
    if main_concept not in ['C1', 'C2']:
         allowed_scope += f"\n- C1: {CONCEPT_DETAILS['C1']}"
         allowed_scope += f"\n- C2: {CONCEPT_DETAILS['C2']}"

    system_prompt = f"""
    【角色設定】你是 Python 程式架構教學專家，專門設計「程式架構教學 (Architecture Scaffolding)」。

    【核心概念】：{main_concept} ({CONCEPT_DETAILS.get(main_concept, "")})

    【允許使用的語法範圍】：
    {allowed_scope}

    【任務目標】
    請使用提供的【標準解答】，設計一個「單一結構化」的程式碼架構模板 (Architecture Template)。
    
    🔥 【分解規範】
    1. **Code (程式碼)**：提供一個包含「挖空」或「註解提示」的程式碼模板 (Template)，讓學生可以填空。
       - 例如： `for i in range(____): # 請填入次數`
       - 或保留關鍵結構，讓學生填寫細節。
    2. **完整性**：模板應覆蓋解題的關鍵架構。
    3. **語法限制**：程式碼部分必須符合允許的語法範圍。

    【輸出規範】
    請直接輸出 JSON 格式，包含 `code` (字串) 欄位即可。
    """

    user_prompt = f"""
    【標準解答內容】
    {solution_code if solution_code else "# 無提供標準解答"}

    【原始題目資訊】
    ID: {problem_id}
    標題：{title}
    描述：{desc}
    輸入說明：{in_desc}
    輸出說明：{out_desc}
    範例數據：{samples}
    """
    
    if not solution_code or solution_code == "# No solution code provided":
         pass
         
    try:
        completion = openai_client.beta.chat.completions.parse(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ArchitectureQuestion,
            temperature=0.2,
        )
        return completion.choices[0].message.parsed.model_dump() # Return dict
    except Exception as e:
        print(f"  ❌ AI 生成失敗: {e}")
        return None
