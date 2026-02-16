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
    id: int = Field(..., description="選項編號 (1~4)")
    label: str = Field(..., description="選項內容 (必須是對程式功能的自然語言描述，例如：'計算兩數之和')")
    feedback: str = Field(..., description="選項回饋 (解釋為何該描述正確或錯誤)")

class CodeContent(BaseModel):
    content: str = Field(..., description="程式碼片段。注意：必須是正確的程式碼，但嚴格禁止與原題情境相同並且複雜度須下降。")

class QuestionContent(BaseModel):
    text: str = Field(..., description="題目敘述 (固定為：'這段程式碼的主要功能是什麼？')")
    code: CodeContent = Field(..., description="程式碼物件")

class AnswerConfig(BaseModel):
    correct_id: int = Field(..., description="正確選項 ID")
    explanation: str = Field(..., description="完整詳解")

class ExplanationQuestion(BaseModel):
    id: str = Field(..., description="題目編號 (Q1)")
    type: str = Field("code_explanation", description="固定為 code_explanation")
    targeted_concept: str = Field(..., description="此題針對的觀念拆解")
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

def generate_explanation_questions(problem_data, problem_id, manual_unit=None):
    # problem_data format: (title, description, input_description, output_description, samples, [solution_code])
    if len(problem_data) == 6:
        title, desc, in_desc, out_desc, samples, solution_code = problem_data
    else:
        title, desc, in_desc, out_desc, samples = problem_data[:5]
    
    unit_id = manual_unit if manual_unit else get_unit_from_id(problem_id)
    unit_topic = CONCEPT_DETAILS.get(unit_id, "Python 基礎")
    
    # 建立允許使用的語法範圍 string
    # Assuming valid_concept_ids is all concepts up to current unit? Or just the current unit?
    # In the notebook, it passed CONCEPT_FILTER list.
    # Here let's assume we want to focus on the current unit, but maybe allowed scope includes previous?
    # For now, let's just use the current unit and maybe C1-C8 if passed.
    # To keep it simple and independent, let's just use all concepts if no specific filter is provided, 
    # OR follow the notebook logic which seemingly expected a list.
    # But here we might just have one unit ID. 
    # Let's adapt to use logical scope: current unit + previous units? 
    # Actually the notebook `CONCEPT_FILTER = ["C4", "C8", ...]` implies prioritized list.
    # Let's just use the unit_id provided as the main concept.
    
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

    【當前教學單元】：**{unit_id}: {unit_topic}**
    
    【任務目標】
    請針對【原始題目資訊】的核心觀念，設計 **1 題** 「程式碼行為解釋 (Behavior Description)」選擇題。選項最多**3個**
    讓學生在 **不寫程式** 的情況下，透過閱讀程式碼來理解解題邏輯。

    🔥 **絕對防洩題機制 (Anti-Leak Rules) - 違反者即刻失敗** 🔥
    1. **情境置換 (Scenario Shift)**：
       - 生成的程式碼 (`code.content`) **絕對不可** 使用與原題相同的情境與相同複雜度。
       - **範例**：
         - 原題：計算「BMI」(體重/身高^2)。
         - 生成題：必須改為計算「長方形面積」(長*寬) 或 「平均分數」(總分/3)。
         - **邏輯 (數學運算結構) 概念相似(複雜度須下降)！**
    
    2. **變數混淆 (Variable Obfuscation)**：
       - **嚴禁** 使用原題描述中出現的變數名稱（如 input/output description 提到的變數）。
       - 請使用通用的變數名稱 (如 `a`, `b`, `x`, `total`, `result`) 或全新情境的變數 (如 `price`, `discount`)。

    3. **禁止提供解答**：
       - 題目中的程式碼 **不能** 是原題目的直接解答。學生如果直接複製這段程式碼去提交原題，**必須是 0 分 (Wrong Answer)**。

    【生成步驟】
    1. **提取核心邏輯**：分析原題用到什麼邏輯？(例如：交換變數、字串串接、取餘數判斷奇偶)。
    2. **創造新情境**：用一個完全不同的生活例子來包裝這個邏輯。
    3. **撰寫程式碼**：寫出新情境下的正確程式碼。
    4. **設計選項**：選項必須是「自然語言的功能描述」，說明這段程式碼在做什麼。

    【輸出規範】
    請直接輸出 JSON 格式。
    """

    user_prompt = f"""
    【原始題目資訊】
    ID: {problem_id}
    標題：{title}
    描述：{desc}
    輸入說明：{in_desc}
    輸出說明：{out_desc}
    範例數據：{samples}

    請依照「防洩題機制」進行情境置換，並生成一題行為解釋題目 (JSON)。
    """

    try:
        completion = openai_client.beta.chat.completions.parse(
            model="gpt-4o", 
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
