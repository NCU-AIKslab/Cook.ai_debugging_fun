import asyncio
import json
from dotenv import load_dotenv
from backend.app.agents.teacher_agent.critics.quality_critic import QualityCritic
from backend.app.agents.teacher_agent.skills.exam_generator.exam_nodes import get_llm

load_dotenv()

async def test_grammatical_rubric():
    """
    Test Grammatical rubric with spelling errors and punctuation issues.
    """
    print("=== Testing Grammatical Rubric ===\n")
    
    llm = get_llm()
    critic = QualityCritic(llm, threshold=4.0)
    
    # Test Case 1: Severe spelling error (1 point expected)
    print("Test Case 1: 嚴重拼寫錯誤（專業術語拼錯）")
    print("=" * 70)
    
    spelling_error_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 8,
            "question_text": "使用 P施來替代維度，這叫什麼？",
            "options": {
                "A": "數據清洗",
                "B": "數據集成",
                "C": "降維",
                "D": "數據轉換"
            },
            "correct_answer": "C",
            "source": {
                "page_number": "25",
                "evidence": "PCA 降維到 2 個主要成分。"
            }
        }]
    }
    
    result1 = await critic.evaluate(spelling_error_case, criteria=["Grammatical"])
    
    print(f"題目: {spelling_error_case['questions'][0]['question_text']}")
    print(f"問題: 「P施」應為「PCA」")
    print(f"Evidence: {spelling_error_case['questions'][0]['source']['evidence']}\n")
    
    if "evaluations" in result1:
        for eval_item in result1["evaluations"]:
            print(f"📊 評分: {eval_item['rating']}/5 (預期 1-2 分)")
            print(f"分析: {eval_item['analysis'][:200]}...")
            if eval_item.get('suggestions'):
                print(f"\n建議:")
                for sug in eval_item['suggestions'][:3]:
                    print(f"  - {sug}")
    
    # Test Case 2: Multiple spelling errors + missing punctuation (2 points expected)
    print("\n\n" + "=" * 70)
    print("Test Case 2: 多處錯別字 + 標點缺失")
    print("=" * 70)
    
    multiple_errors_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 1,
            "question_text": "機器學習中特徵工程的目地是什麼它可以幫助模形提高準確率",
            "options": {
                "A": "增加數據量",
                "B": "選擇和建構有效特徵",
                "C": "減少訓練時間",
                "D": "避免過擬合"
            },
            "correct_answer": "B",
            "source": {
                "page_number": "15",
                "evidence": "特徵工程是選擇和建構有效特徵的過程。"
            }
        }]
    }
    
    result2 = await critic.evaluate(multiple_errors_case, criteria=["Grammatical"])
    
    print(f"題目: {multiple_errors_case['questions'][0]['question_text']}")
    print("問題:")
    print("  - 「目地」應為「目的」")
    print("  - 「模形」應為「模型」")
    print("  - 缺少問號和逗號\n")
    
    if "evaluations" in result2:
        for eval_item in result2["evaluations"]:
            print(f"📊 評分: {eval_item['rating']}/5 (預期 1-2 分)")
            print(f"分析: {eval_item['analysis'][:200]}...")
            if eval_item.get('suggestions'):
                print(f"\n建議數量: {len(eval_item['suggestions'])}")
    
    # Test Case 3: Minor punctuation issue (3 points expected)
    print("\n\n" + "=" * 70)
    print("Test Case 3: 輕微標點問題")
    print("=" * 70)
    
    minor_issue_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 1,
            "question_text": "在資料清洗中,處理缺失值的常見方法包括哪些。",
            "options": {
                "A": "刪除含缺失值的行",
                "B": "使用平均值填補",
                "C": "使用回歸模型預測",
                "D": "以上皆是"
            },
            "correct_answer": "D",
            "source": {
                "page_number": "10",
                "evidence": "處理缺失值的方法包括刪除、填補和預測。"
            }
        }]
    }
    
    result3 = await critic.evaluate(minor_issue_case, criteria=["Grammatical"])
    
    print(f"題目: {minor_issue_case['questions'][0]['question_text']}")
    print("問題:")
    print("  - 逗號應為全形「，」")
    print("  - 句尾應為問號「？」而非句號\n")
    
    if "evaluations" in result3:
        for eval_item in result3["evaluations"]:
            print(f"📊 評分: {eval_item['rating']}/5 (預期 3-4 分)")
            print(f"分析: {eval_item['analysis'][:150]}...")
    
    # Test Case 4: Perfect grammar (4-5 points expected)
    print("\n\n" + "=" * 70)
    print("Test Case 4: 語法完美")
    print("=" * 70)
    
    perfect_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 1,
            "question_text": "PCA（主成分分析）的主要目的為何？",
            "options": {
                "A": "增加資料維度",
                "B": "降維以簡化分析",
                "C": "處理缺失值",
                "D": "移除異常值"
            },
            "correct_answer": "B",
            "source": {
                "page_number": "25",
                "evidence": "PCA 主要用於降維。"
            }
        }]
    }
    
    result4 = await critic.evaluate(perfect_case, criteria=["Grammatical"])
    
    print(f"題目: {perfect_case['questions'][0]['question_text']}")
    print("狀況: 無拼寫錯誤、標點正確\n")
    
    if "evaluations" in result4:
        for eval_item in result4["evaluations"]:
            print(f"📊 評分: {eval_item['rating']}/5 (預期 4-5 分)")
            print(f"分析: {eval_item['analysis'][:150]}...")
    
    print("\n" + "=" * 70)
    print("✅ Grammatical Rubric 測試完成")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_grammatical_rubric())
