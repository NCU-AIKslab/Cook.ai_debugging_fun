import os
import json
from typing import List, Optional
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

# ================= 2. 定義資料結構 (Pydantic Schema) =================

class Option(BaseModel):
    id: int
    label: str
    feedback: str

class CodeContent(BaseModel):
    content: str

class QuestionContent(BaseModel):
    text: str = "這段程式碼的主要功能是什麼？"
    code: CodeContent

class AnswerConfig(BaseModel):
    correct_id: int
    explanation: str

class ExplanationQuestion(BaseModel):
    id: str
    type: str = "code_explanation"
    targeted_concept: str
    options: List[Option]
    question: QuestionContent
    answer_config: AnswerConfig

class ExplanationQuestionResponse(BaseModel):
    questions: List[ExplanationQuestion]

# ================= 3. 核心生成邏輯 =================

def get_unit_from_id(problem_id: str) -> str:
    if "_" in problem_id:
        return problem_id.split("_")[0]
    return "C1"

def generate_explanation_questions(problem_data, problem_id, manual_unit=None, allowed_concepts=None):
    # problem_data format: (title, description, input_description, output_description, samples, [solution_code])
    if len(problem_data) == 6:
        title, desc, in_desc, out_desc, samples, solution_code = problem_data
    else:
        title, desc, in_desc, out_desc, samples = problem_data[:5]
    
    unit_id = manual_unit if manual_unit else get_unit_from_id(problem_id)
    unit_topic = CONCEPT_DETAILS.get(unit_id, "Python 基礎")
    
    if allowed_concepts:
        # User manual selection
        allowed_scope = ""
        for c in allowed_concepts:
            if c in CONCEPT_DETAILS:
                allowed_scope += f"- {c}: {CONCEPT_DETAILS[c]}\n"
    else:
        # Default auto logic
        allowed_scope = f"- {unit_id}: {unit_topic}"
        # Maybe add basic concepts C1, C2 if not C1/C2?
        if unit_id not in ['C1', 'C2']:
            allowed_scope += f"\n- C1: {CONCEPT_DETAILS['C1']}"
            allowed_scope += f"\n- C2: {CONCEPT_DETAILS['C2']}"

    json_example_str = """
    [
        {
            "id": "Q1",
            "type": "code_explanation",
            "targeted_concept": "變數交換邏輯",
            "options": [
                { "id": 1, "label": "將兩個變數的數值進行交換", "feedback": "✅ 正確：透過暫存變數 temp，成功互換了 x 與 y 的值。" },
                { "id": 2, "label": "將兩個變數都設為相同的值", "feedback": "❌ 錯誤：這不是賦值，而是交換。" },
                { "id": 3, "label": "計算兩個變數的總和", "feedback": "❌ 錯誤：程式碼中沒有進行加法運算。" }
            ],
            "question": {
                "text": "這段程式碼的主要功能是什麼？",
                "code": {
                    "content": "temp = x\\ncan_print = True"
                }
            },
            "answer_config": {"correct_id": 1, "explanation": "使用第三個變數作為暫存區..."}
        }
    ]
    """

    system_prompt = f"""
    【角色設定】你是 Python 程式教學專家，專精於引導初學者進行「程式碼閱讀理解 (Code Comprehension)」。

    【核心概念】：**{unit_id}: {unit_topic}**

    【允許使用的語法範圍】：
    {allowed_scope}

    【嚴格限制】：
    生成的程式碼內容 **絕對不能超出** 以上提供的「允許使用的語法範圍」。如果範圍內沒有提到迴圈(C5/C6)或判斷式(C4)，則程式碼中嚴禁出現相關語法。

    【任務目標】
    請針對【原始題目資訊】中的「核心運算邏輯」，拆解出一個**子題目（關鍵邏輯片段）**。
    設計 **1 題** 「程式碼行為解釋 (Behavior Description)」選擇題，選項最多 **3 個**。
    此題旨在讓學生專注理解該原題背後的純程式邏輯或數學轉換，**不需加入任何生活情境包裝**。

    **絕對邏輯拆解機制 (Logic Deconstruction Rules)**
    1. **去情境化 (Pure Logic Only)**：
    - 程式碼應呈現純粹的邏輯運算。**不要**提到原題的背景（例如：不要提到 BMI、餐費、超市）。
    - 變數名稱應保持抽象（如 `a`, `b`, `ans`, `val`, `temp`）。
    
    2. **關鍵邏輯子集 (Key Logic Sub-task)**：
    - 程式碼必須是原題目的「核心零件」。例如：
        - 原題是「計算折扣後金額」，子題目程式碼應專注於「百分比的乘法運算」。
        - 原題是「判斷閏年」，子題目程式碼應專注於「取餘數 `%` 的邏輯」。
    - **複雜度必須低於原題**，只取原題中最關鍵的一步。

    3. **禁止提供完整解答**：
    - 題目中的程式碼僅為片段，**不能**是原題目的完整解答。直接複製此片段去提交原題必須無法過關。

    【生成步驟】
    1. **提取核心邏輯**：從原題中識別出最關鍵的運算邏輯（例如：單位換算、字串拼接、特定算式）。
    2. **邏輯純化**：移除所有描述性文字與情境變數，將其轉化為簡單的變數運算。
    3. **撰寫程式碼**：寫出該關鍵邏輯的純淨程式碼片段。
    4. **設計選項**：選項必須是「自然語言的行為描述」，說明這段程式碼在對資料進行什麼樣的處理。

    【輸出規範】
    請直接輸出 JSON 格式，結構需符合：
    {json_example_str}
    """

    user_prompt = f"""
    【原始題目資訊】
    ID: {problem_id}
    標題：{title}
    描述：{desc}
    輸入說明：{in_desc}
    輸出說明：{out_desc}
    範例數據：{samples}
    """

    try:
        completion = openai_client.beta.chat.completions.parse(
            model="gpt-5.1", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ExplanationQuestionResponse,
            temperature=0.2,
        )

        parsed_obj = completion.choices[0].message.parsed
        return [q.model_dump() for q in parsed_obj.questions]

    except Exception as e:
        print(f"❌ 生成失敗: {e}")
        return None
