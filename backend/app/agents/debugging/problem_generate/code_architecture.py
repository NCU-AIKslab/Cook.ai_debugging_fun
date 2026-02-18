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

class ArchitectureQuestion(BaseModel):
    code: str = Field(..., description="挖空後的程式碼框架")

# ================= 3. AI 生成邏輯 =================

def get_unit_from_id(problem_id: str) -> str:
    if "_" in problem_id:
        return problem_id.split("_")[0]
    return "C1"

def generate_architecture_questions(problem_data, problem_id, manual_unit=None, allowed_concepts=None):
    # Expecting problem_data to have solution_code at the end
    if len(problem_data) == 6:
        title, desc, in_desc, out_desc, samples, solution_code = problem_data
    else:
        # Fallback if no solution code provided (should be handled by caller)
        title, desc, in_desc, out_desc, samples = problem_data[:5]
        solution_code = "# No solution code provided"
        
    main_concept = manual_unit if manual_unit else get_unit_from_id(problem_id)
    
    if allowed_concepts:
        # User manual selection
        allowed_scope = ""
        for c in allowed_concepts:
            if c in CONCEPT_DETAILS:
                allowed_scope += f"- {c}: {CONCEPT_DETAILS[c]}\n"
    else:
        # Default auto logic
        allowed_scope = f"- {main_concept}: {CONCEPT_DETAILS.get(main_concept, '')}"
        if main_concept not in ['C1', 'C2']:
             allowed_scope += f"\n- C1: {CONCEPT_DETAILS['C1']}"
             allowed_scope += f"\n- C2: {CONCEPT_DETAILS['C2']}"

    json_example_str = """
    {
    "code": "n = int(input())\nprime_count = 0  # 用來記錄找到幾個質數\n\n# 外層迴圈：遍歷每一個數字\nfor num in range(2, _____):   # ← 設定正確範圍\n    is_prime = True           # 先假設 num 是質數（立起旗標）\n\n    # 內層迴圈：檢查因數\n    for divisor in range(2, num):\n        if __________________:   # ← 填寫整除條件\n            is_prime = False\n            break                # 不是質數，後面不用檢查\n\n    if is_prime == True:\n        __________________      # ← 發現一個質數\n\nprint(f\"1 到 {n} 之間共有 {prime_count} 個質數\")"
    }
    """

    system_prompt = f"""
    【角色設定】你是 Python 程式架構教學專家，專門設計「程式填空題 (Code Cloze)」。

    【核心概念】：{main_concept} ({CONCEPT_DETAILS.get(main_concept)})

    【允許使用的語法範圍】：
    {allowed_scope}

    【任務目標】
    請使用提供的【標準解答】，將其中關於「{main_concept}」或相關範圍的關鍵邏輯處挖空（使用 '_____' 代替）。
    
    🔥 【挖空規範】
    1. 使用原題解答：`code` 必須基於提供的標準解答，不可改編變數名或邏輯。
    2. 關鍵處挖空：將核心演算法、邊界條件或關鍵函式挖空。挖空數量為 2~5 個。
    3. 語法限制：挖空以外的程式碼部分，**絕對不能超出** 上述允許的語法範圍。
    4. 挖空深度：底線的長度應視被取代的程式碼內容長度而定，使其看起來自然。

    【輸出規範】
    請直接輸出 JSON 格式，結構需符合：
    {json_example_str}
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
            model="gpt-5.1", 
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
