import asyncio
import json
from dotenv import load_dotenv
from backend.app.agents.teacher_agent.critics.fact_critic import (
    CustomFaithfulness, 
    TaskSatisfaction,
    get_fact_critic_llm
)

load_dotenv()

async def test_fact_critic():
    """
    Test Ragas-based Faithfulness and rule-based TaskSatisfaction metrics.
    """
    print("=== Testing Fact Critic (Faithfulness + TaskSatisfaction) ===\n")
    
    # Initialize LLM using Cook.ai settings
    llm = get_fact_critic_llm()
    
    # Initialize metrics
    faithfulness = CustomFaithfulness()
    faithfulness.llm = llm
    
    task_satisfaction = TaskSatisfaction()
    
    # Test Case 1: High quality answer (Faithfulness)
    print("Test Case 1: High Quality Answer (Faithful)")
    print("-" * 60)
    
    row1 = {
        "user_input": "PCA（主成分分析）的主要目的為何？",
        "response": "PCA 的主要用途是將數據降維到較少的主要成分，以簡化數據的分析。",
        "retrieved_contexts": [
            "PCA的主要用途是將數據降維到較少的主要成分，以簡化數據的分析。",
            "主成分分析（PCA）是統計學中常用的降維技術。"
        ]
    }
    
    print(f"Question: {row1['user_input']}")
    print(f"Answer: {row1['response']}")
    print(f"Contexts: {len(row1['retrieved_contexts'])} items\n")
    
    f_result1 = await faithfulness.score_with_feedback(row1)
    
    print(f"Faithfulness Score: {f_result1['normalized_score']}/5 (raw: {f_result1['score']:.2f})")
    print(f"Analysis: {f_result1['analysis'][:100]}...")
    
    # Test Case 2: Low quality answer (unfaithful)
    print("\n\n" + "=" * 60)
    print("Test Case 2: Unfaithful Answer (Contains Unsupported Claims)")
    print("-" * 60)
    
    row2 = {
        "user_input": "PCA（主成分分析）的主要目的為何？",
        "response": "PCA 用於增加數據的維度並提高預測準確性，它是深度學習中最常用的方法。",
        "retrieved_contexts": [
            "PCA的主要用途是將數據降維到較少的主要成分，以簡化數據的分析。"
        ]
    }
    
    print(f"Question: {row2['user_input']}")
    print(f"Answer: {row2['response']}")
    print(f"Contexts: {len(row2['retrieved_contexts'])} items\n")
    
    f_result2 = await faithfulness.score_with_feedback(row2)
    
    print(f"Faithfulness Score: {f_result2['normalized_score']}/5 (raw: {f_result2['score']:.2f})")
    print(f"Analysis: {f_result2['analysis'][:100]}...")
    if f_result2['suggestions']:
        print("Suggestions:")
        for s in f_result2['suggestions']:
            print(f"  - {s}")
    
    # Test Case 3: TaskSatisfaction - Exam Generation
    print("\n\n" + "=" * 60)
    print("Test Case 3: TaskSatisfaction - Exam Generation")
    print("-" * 60)
    
    user_query = "出兩題關於 PCA 的選擇題"
    generated_content = [
        {
            "type": "multiple_choice",
            "questions": [
                {
                    "question_text": "PCA 的主要用途是什麼？",
                    "type": "multiple_choice",
                    "options": {"A": "增加維度", "B": "降低維度", "C": "分類", "D": "聚類"},
                    "correct_answer": "B",
                    "source": {"page_number": 1, "evidence": "PCA 用於降維..."}
                },
                {
                    "question_text": "PCA 屬於哪種學習方法？",
                    "type": "multiple_choice",
                    "options": {"A": "監督學習", "B": "非監督學習", "C": "強化學習", "D": "深度學習"},
                    "correct_answer": "B",
                    "source": {"page_number": 2, "evidence": "PCA 是非監督學習..."}
                }
            ]
        }
    ]
    
    print(f"User Query: {user_query}")
    print(f"Generated: {len(generated_content[0]['questions'])} questions\n")
    
    task_result = await task_satisfaction.evaluate(
        user_query=user_query,
        generated_content=generated_content,
        task_type="exam_generation"
    )
    
    print(f"TaskSatisfaction Score: {task_result['normalized_score']}/5 (ratio: {task_result['score']:.2f})")
    print(f"Weighted Score: {task_result['weighted_score']}/{task_result['total_weight']}")
    print(f"Analysis: {task_result['analysis']}")
    print("\nChecks:")
    for check in task_result['checks']:
        status = "PASS" if check['passed'] else "FAIL"
        print(f"  [{status}] {check['name']} (weight: {check['weight']})")
        if 'expected' in check:
            print(f"      Expected: {check['expected']}, Actual: {check.get('actual', 'N/A')}")
    
    # Test Case 4: TaskSatisfaction - Wrong Count
    print("\n\n" + "=" * 60)
    print("Test Case 4: TaskSatisfaction - Wrong Question Count")
    print("-" * 60)
    
    user_query2 = "出三題關於 PCA 的選擇題"  # Asks for 3 but we only have 2
    
    task_result2 = await task_satisfaction.evaluate(
        user_query=user_query2,
        generated_content=generated_content,  # Same content (2 questions)
        task_type="exam_generation"
    )
    
    print(f"User Query: {user_query2}")
    print(f"Generated: 2 questions (expected 3)\n")
    print(f"TaskSatisfaction Score: {task_result2['normalized_score']}/5")
    print(f"Analysis: {task_result2['analysis']}")
    if task_result2['suggestions']:
        print("Suggestions:")
        for s in task_result2['suggestions']:
            print(f"  - {s}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_fact_critic())

