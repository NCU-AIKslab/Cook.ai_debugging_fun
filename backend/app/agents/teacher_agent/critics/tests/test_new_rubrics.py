import asyncio
import json
from dotenv import load_dotenv
from backend.app.agents.teacher_agent.critics.quality_critic import QualityCritic
from backend.app.agents.teacher_agent.skills.exam_generator.exam_nodes import get_llm

load_dotenv()

# Mock RAG context - 模擬真實教材內容
MOCK_RAG_CONTEXT = """
第10頁：資料清洗與缺失值處理

在實際的資料集中，我們常常會遇到缺失值（Missing Values）的問題。例如，在一份包含年齡（Age）、收入（Income）、教育程度（Education）的問卷調查資料中，部分受訪者可能沒有填寫年齡欄位，導致該欄位出現空白。

處理缺失值的常見方法包括：
1. 刪除法：直接刪除包含缺失值的整筆資料
2. 填補法：使用統計值填補，如平均數（Mean）、中位數（Median）、眾數（Mode）
3. 預測法：利用回歸模型（Regression Model）或 KNN 算法預測缺失值

在我們的範例資料集中，年齡（Age）欄位有 15% 的缺失值。經過分析後，我們決定使用中位數（Median）來填補年齡的缺失值，因為中位數不受極端值影響，較為穩健。

第25頁：主成分分析（PCA）

主成分分析（Principal Component Analysis, PCA）是一種常用的降維技術。當資料集包含過多特徵時（例如 100 個特徵），PCA 可以將這些特徵壓縮成較少的主要成分（例如 3-5 個），同時保留大部分的資訊。

PCA 的主要目的：
- 降低資料維度，簡化後續分析
- 去除特徵間的相關性
- 便於資料視覺化

範例：在一個房價預測專案中，我們原本有 20 個特徵（坪數、房間數、屋齡等），使用 PCA 降維到 2 個主要成分後，可以更容易地將資料繪製成二維散佈圖。
"""

async def test_new_rubric_structure():
    """
    Test new rubric structure with mock RAG context.
    Tests all 4 criteria: Understandable, Grammatical, Logical_Consistency, Phrasing
    """
    print("=== Testing New Rubric Structure with Mock RAG Context ===\n")
    
    llm = get_llm()
    critic = QualityCritic(llm, threshold=4.0)
    
    # Test Case 1: Missing Context (Understandable issue)
    print("Test Case 1: 缺乏情境說明 (Understandable)")
    print("=" * 70)
    
    missing_context_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 6,
            "question_text": "對於薪水的填補，通常使用什麼值？",
            "options": {
                "A": "最大值",
                "B": "最小值",
                "C": "平均值",
                "D": "中位數"
            },
            "correct_answer": "D",
            "source": {
                "page_number": "13",
                "evidence": "薪水 (Salary) 列填補為中位數。"
            },
            "rag_context": MOCK_RAG_CONTEXT  # 加入 RAG context
        }]
    }
    
    print(f"題目: {missing_context_case['questions'][0]['question_text']}")
    print(f"問題分析:")
    print(f"  1. 缺乏「為什麼薪水需要填補」的背景（資料有缺失值）")
    print(f"  2. 缺乏「為什麼選擇中位數」的理由（薪水有極端值）")
    print(f"  3. 「通常」一詞模糊不清")
    print(f"  4. 學生無法理解題目的情境和目的\n")
    
    result1 = await critic.evaluate(missing_context_case, criteria=["Understandable"])
    
    if "evaluations" in result1:
        for eval_item in result1["evaluations"]:
            print(f"📊 評分: {eval_item['rating']}/5 (預期 2-3 分)")
            print(f"分析: {eval_item['analysis'][:250]}...")
            if eval_item.get('suggestions'):
                print(f"\n建議: {len(eval_item['suggestions'])} 項")
                for i, sug in enumerate(eval_item['suggestions'][:3], 1):
                    print(f"  {i}. {sug}")
    
    # Test Case 2: Answer Contradiction (Logical_Consistency issue)
    print("\n\n" + "=" * 70)
    print("Test Case 2: 答案與參考資料矛盾 (Logical_Consistency)")
    print("=" * 70)
    
    contradiction_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 1,
            "question_text": "在範例資料集中，填補年齡缺失值使用的方法為何？",
            "options": {
                "A": "中位數",
                "B": "平均數",
                "C": "眾數",
                "D": "回歸模型"
            },
            "correct_answer": "B",  # 錯誤！應該是 A
            "source": {
                " number": "10",
                "evidence": "我們決定使用中位數（Median）來填補年齡的缺失值。"
            },
            "rag_context": MOCK_RAG_CONTEXT
        }]
    }
    
    print(f"題目: {contradiction_case['questions'][0]['question_text']}")
    print(f"正確答案: B (平均數)")
    print(f"Evidence: 使用中位數填補")
    print(f"→ 矛盾！\n")
    
    result2 = await critic.evaluate(contradiction_case, criteria=["Logical_Consistency"])
    
    if "evaluations" in result2:
        for eval_item in result2["evaluations"]:
            print(f"📊 評分: {eval_item['rating']}/5 (預期 1 分)")
            print(f"分析: {eval_item['analysis'][:200]}...")
            if eval_item.get('suggestions'):
                print(f"\n建議:")
                for sug in eval_item['suggestions'][:2]:
                    print(f"  - {sug}")
    
    # Test Case 3: Spelling Error (Grammatical issue)
    print("\n\n" + "=" * 70)
    print("Test Case 3: 專業術語拼寫錯誤 (Grammatical)")
    print("=" * 70)
    
    spelling_error_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 1,
            "question_text": "P施降維的主要目的為何？",
            "options": {
                "A": "增加特徵數量",
                "B": "降低資料維度",
                "C": "填補缺失值",
                "D": "移除異常值"
            },
            "correct_answer": "B",
            "source": {
                "page_number": "25",
                "evidence": "PCA 的主要目的：降低資料維度"
            },
            "rag_context": MOCK_RAG_CONTEXT
        }]
    }
    
    print(f"題目: {spelling_error_case['questions'][0]['question_text']}")
    print(f"錯誤: 「P施」應為「PCA」\n")
    
    result3 = await critic.evaluate(spelling_error_case, criteria=["Grammatical"])
    
    if "evaluations" in result3:
        for eval_item in result3["evaluations"]:
            print(f"📊 評分: {eval_item['rating']}/5 (預期 1-2 分)")
            print(f"分析: {eval_item['analysis'][:150]}...")
    
    # Test Case 4: Mainland Chinese Terms (Phrasing issue)
    print("\n\n" + "=" * 70)
    print("Test Case 4: 大陸用語 (Phrasing)")
    print("=" * 70)
    
    mainland_terms_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 1,
            "question_text": "在机器学习中，数据清洗的主要目的是什么？",
            "options": {
                "A": "提高数据质量",
                "B": "减少数据量",
                "C": "增加特征",
                "D": "删除所有缺失值"
            },
            "correct_answer": "A",
            "source": {
                "page_number": "10",
                "evidence": "資料清洗的目的是提高資料品質。"
            },
            "rag_context": MOCK_RAG_CONTEXT
        }]
    }
    
    print(f"題目: {mainland_terms_case['questions'][0]['question_text']}")
    print(f"問題: 「机器学习」→「機器學習」、「数据」→「資料」、「质量」→「品質」\n")
    
    result4 = await critic.evaluate(mainland_terms_case, criteria=["Phrasing"])
    
    if "evaluations" in result4:
        for eval_item in result4["evaluations"]:
            print(f"📊 評分: {eval_item['rating']}/5 (預期 1-2 分)")
            print(f"分析: {eval_item['analysis'][:200]}...")
            if eval_item.get('suggestions'):
                print(f"\n建議: {len(eval_item['suggestions'])} 項")
    
    print("\n" + "=" * 70)
    print("✅ 新 Rubric 結構測試完成")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_new_rubric_structure())
