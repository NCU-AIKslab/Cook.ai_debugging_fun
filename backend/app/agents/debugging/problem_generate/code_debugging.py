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

class Option(BaseModel):
    id: int
    label: str
    feedback: str

class CodeContent(BaseModel):
    content: str

class QuestionContent(BaseModel):
    text: str
    code: CodeContent

class AnswerConfig(BaseModel):
    correct_id: int
    explanation: str

class DebuggingQuestion(BaseModel):
    id: str
    type: str = "debugging"
    targeted_concept: str
    options: List[Option]
    question: QuestionContent
    answer_config: AnswerConfig

class DebuggingQuestionResponse(BaseModel):
    questions: List[DebuggingQuestion]

# ================= 3. AI 生成邏輯 =================

def get_unit_from_id(problem_id: str) -> str:
    if "_" in problem_id:
        return problem_id.split("_")[0]
    return "C1"

def generate_debugging_questions(problem_data, problem_id, manual_unit=None, allowed_concepts=None):
    if len(problem_data) == 6:
        title, desc, in_desc, out_desc, samples, solution_code = problem_data
    else:
        title, desc, in_desc, out_desc, samples = problem_data[:5]
    
    # Determine concepts
    main_concept = manual_unit if manual_unit else get_unit_from_id(problem_id)
    
    # Construct allowed scope text
    if allowed_concepts:
        # User manual selection
        allowed_scope = ""
        for c in allowed_concepts:
            if c in CONCEPT_DETAILS:
                allowed_scope += f"- {c}: {CONCEPT_DETAILS[c]}\n"
    else:
        allowed_scope = f"- {main_concept}: {CONCEPT_DETAILS.get(main_concept, '')}"
        if main_concept not in ['C1', 'C2']:
             allowed_scope += f"\n- C1: {CONCEPT_DETAILS['C1']}"
             allowed_scope += f"\n- C2: {CONCEPT_DETAILS['C2']}"

    json_example_str = """
    [
        {
            "id": "Q1",
            "type": "debugging",
            "options": [
                {
                    "id": 1, 
                    "label": "第2行程式會產生型態錯誤，因為無法將文字與數字直接相加", 
                    "feedback": "✅ 正確：input() 讀入的是字串，必須先轉成整數才能運算。"
                },
                {
                    "id": 2, 
                    "label": "程式會順利執行，並將數字 5 接在輸入的文字後面", 
                    "feedback": "❌ 錯誤：Python 不允許字串(str)與整數(int)直接使用 + 號運算。"
                }
            ],
            "question": {
                "code": {
                    "content": "x = input('Enter number: ')\\nprint(x + 5)"
                },
                "text": "若使用者輸入 10，執行下列程式碼會發生什麼結果？"
            },
            "answer_config": {"correct_id": 1, "explanation": "input() 函式回傳的是字串..."}
        }
    ]
    """

    system_prompt = f"""
    【角色設定】你是 Python 程式教學專家，專門設計「除錯 (Debugging)」訓練。

    【核心概念】：{main_concept} ({CONCEPT_DETAILS.get(main_concept)})
    【允許使用的語法範圍】：
    {allowed_scope}

    【任務目標】
    請針對【原題資訊】中的核心運算邏輯，設計一個「子任務」除錯題：
    1. **子任務描述**：在 `question.text` 中說明這段程式碼「預計要完成的任務」。
    2. **錯誤程式碼**：在 `code.content` 提供一段帶有錯誤(Bug)的程式碼，導致其無法完成上述任務。
    3. **除錯選擇題**：設計最多 3 個選項，讓學生找出錯誤原因。

    【絕對邏輯拆解機制】
    1. **去情境化 (Pure Logic)**：禁止提及原題背景（如 BMI、餐費）。變數名必須抽象化（如 a, b, res, val）。
    2. **關鍵邏輯子集**：程式碼僅呈現原題最核心的「運算零件」。例如：原題算平均，子任務應專注於「總和除以數量」的邏輯。
    3. **語法嚴格限制**：生成的程式碼 **絕對不能超出** 提供的語法範圍。
    4. **必定包含 Bug**：程式碼必須包含一個該單元程度的典型錯誤（如型態轉換失敗、邏輯運算子誤用）。
    5. **禁止洩題**：這段程式碼不能是原題的完整解答。

    【生成步驟】
    1. 提取邏輯：分析原題的核心算式或資料處理點。
    2. 設定任務：將該邏輯寫成一個簡單的任務目標。
    3. 植入錯誤：撰寫一段試圖達成任務但包含 Bug 的純淨程式碼。
    4. 設計選項：選項應針對 Bug 的原因進行自然語言描述。

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
            response_format=DebuggingQuestionResponse,
            temperature=0.2,
        )
        parsed_obj = completion.choices[0].message.parsed
        return [q.model_dump() for q in parsed_obj.questions]
    except Exception as e:
        print(f"AI 生成失敗: {e}")
        return None
