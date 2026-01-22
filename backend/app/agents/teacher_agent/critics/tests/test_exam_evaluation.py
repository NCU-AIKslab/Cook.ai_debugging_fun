import asyncio
import json
from dotenv import load_dotenv
from backend.app.agents.teacher_agent.critics.quality_critic import QualityCritic
from backend.app.agents.teacher_agent.skills.exam_generator.exam_nodes import get_llm

load_dotenv()

# Mock exam with 3 questions
MOCK_EXAM = {
    "type": "multiple_choice",
    "title": "機器學習基礎考試",
    "questions": [
        {
            "question_number": 1,
            "question_text": "PCA（主成分分析）的主要目的為何？",
            "options": {
                "A": "增加資料的維度",
                "B": "降維以簡化資料分析",
                "C": "同時處理多個資料來源",
                "D": "提高資料的準確性"
            },
            "correct_answer": "B",
            "source": {
                "page_number": "25",
                "evidence": "PCA的主要用途是將資料降維到較少的主要成分，以簡化資料的分析。"
            }
        },
        {
            "question_number": 2,
            "question_text": "机器学习中的数据预处理包括哪些步驟？",  # 簡體字問題
            "options": {
                "A": "数据清洗和标准化",
                "B": "数据可视化",
                "C": "模型訓練",
                "D": "以上皆是"
            },
            "correct_answer": "A",
            "source": {
                "page_number": "15",
                "evidence": "资料预处理是机器学习流程中的重要步骤。"
            }
        },
        {
            "question_number": 3,
            "question_text": "填補缺失值的方式之一是使用什麼來填補年齡？",
            "options": {
                "A": "中位數",
                "B": "平均數",
                "C": "眾數",
                "D": "回歸模型"
            },
            "correct_answer": "A",
            "source": {
                "page_number": "10",
                "evidence": "年齡 (Age) 列填補為平均值。"  # 答案矛盾問題
            }
        }
    ]
}

# Mock RAG content
MOCK_RAG_CONTENT = """
PCA（主成分分析）是一種降維技術，用於簡化高維度資料。
在機器學習中，資料預處理包括清洗、標準化等步驟。
處理缺失值時，可以使用平均值、中位數或眾數進行填補。
"""


async def test_evaluate_exam():
    """
    Test evaluate_exam - 整卷評估 + 逐題評估
    """
    print("=" * 80)
    print("Test: Evaluate Exam (Overall + Per-Question)")
    print("=" * 80)
    
    llm = get_llm()
    critic = QualityCritic(llm, threshold=4.0)
    
    result = await critic.evaluate_exam(MOCK_EXAM, rag_content=MOCK_RAG_CONTENT)
    
    print(f"\n結果結構: {list(result.keys())}")
    
    # Overall assessment
    if "overall" in result and "evaluations" in result["overall"]:
        print(f"\n📄 整卷評估:")
        for eval_item in result["overall"]["evaluations"]:
            rating = eval_item['rating']
            emoji = "⚠️" if rating < 4 else "✅"
            print(f"  {emoji} {eval_item['criteria']}: {rating}/5")
    
    # Per-question assessment
    if "per_question" in result:
        print(f"\n📝 逐題評估:")
        for q_result in result["per_question"]:
            q_num = q_result['question_number']
            print(f"\n  第 {q_num} 題:")
            if "evaluations" in q_result:
                for eval_item in q_result["evaluations"]:
                    rating = eval_item['rating']
                    emoji = "⚠️" if rating < 4 else "✅"
                    print(f"    {emoji} {eval_item['criteria']}: {rating}/5")
    
    # Statistics
    if "statistics" in result:
        stats = result["statistics"]
        print(f"\n📊 統計資訊:")
        print(f"  總題數: {stats.get('total_questions', 0)}")
        if stats.get("questions_below_threshold"):
            print(f"  ⚠️ 需要改進的題目: {stats['questions_below_threshold']}")
        
        print(f"\n  平均分數:")
        for criteria, avg in stats.get("avg_scores_by_criteria", {}).items():
            print(f"    • {criteria}: {avg}/5")
    
    return result


async def test_evaluate_single_question():
    """
    Test evaluate_single_question - 單題評估
    """
    print("\n\n" + "=" * 80)
    print("Test: Evaluate Single Question")
    print("=" * 80)
    
    llm = get_llm()
    critic = QualityCritic(llm, threshold=4.0)
    
    # 測試第3題（有矛盾問題）
    question = MOCK_EXAM["questions"][2]
    
    result = await critic.evaluate_single_question(question, rag_content=MOCK_RAG_CONTENT)
    
    print(f"\n評估第 {question['question_number']} 題:")
    
    if "evaluations" in result:
        for eval_item in result["evaluations"]:
            rating = eval_item['rating']
            emoji = "⚠️" if rating < 4 else "✅"
            print(f"\n  {emoji} {eval_item['criteria']}: {rating}/5")
            print(f"     分析: {eval_item['analysis'][:100]}...")
            
            if eval_item.get('suggestions') and rating < 4:
                print(f"     建議: {eval_item['suggestions'][0][:80]}...")
    
    return result


async def main():
    """
    Run all tests
    """
    print("\n🧪 測試 QualityCritic - 簡化版\n")
    
    # Test 1: Evaluate entire exam
    await test_evaluate_exam()
    
    # Test 2: Evaluate single question
    await test_evaluate_single_question()
    
    print("\n\n" + "=" * 80)
    print("✅ 測試完成")
    print("=" * 80)
    print("\n📌 API 使用方式:")
    print("  1. evaluate_exam(exam, rag_content) - 整卷 + 逐題 + 統計")
    print("  2. evaluate_single_question(question, rag_content) - 單題評估")
    print("\n📡 API Server Endpoints:")
    print("  • POST /api/v1/testing/critic/evaluate_exam")
    print("  • POST /api/v1/testing/critic/evaluate_single_question")


if __name__ == "__main__":
    asyncio.run(main())
