import asyncio
import json
from dotenv import load_dotenv
from backend.app.agents.teacher_agent.critics.quality_critic import QualityCritic
from backend.app.agents.teacher_agent.skills.exam_generator.exam_nodes import get_llm

load_dotenv()

async def test_extreme_cases():
    """
    Test with truly terrible (1 point) and excellent (4-5 point) cases.
    """
    print("=== Testing Extreme Cases for Understandable Rubric ===\n")
    
    llm = get_llm()
    critic = QualityCritic(llm, threshold=4.0)
    
    # Test Case 1: TRULY TERRIBLE - Should definitely get 1 point
    print("Test Case 1: 真正糟糕的案例（應得 1 分）")
    print("=" * 70)
    
    terrible_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 1,
            "question_text": "梯度爆炸與 vanishing gradient 在 LSTM 的 cell state 更新中，透過 forget gate 與 input gate 的調節機制，如何影響 backpropagation through time 的穩定性？",
            "options": {
                "A": "透過 gating mechanism 實現 gradient clipping",
                "B": "使用 orthogonal initialization 避免 exploding gradients",
                "C": "Cell state 的 additive update 緩解 vanishing gradients", 
                "D": "Bidirectional RNN 可完全解決此問題"
            },
            "correct_answer": "C",
            "source": {
                "page_number": "1",
                "evidence": "LSTM 架構設計用於處理長序列。"
            }
        }]
    }
    
    result1 = await critic.evaluate(terrible_case, criteria=["Understandable"])
    
    print(f"\n評估結果:")
    if "evaluations" in result1:
        for eval_item in result1["evaluations"]:
            print(f"\n📊 {eval_item['criteria']}")
            print(f"   評分: {eval_item['rating']}/5")
            print(f"   分析: {eval_item['analysis'][:200]}...")
            if eval_item.get('suggestions'):
                print(f"   建議數量: {len(eval_item['suggestions'])}")
                for i, sug in enumerate(eval_item['suggestions'][:2], 1):
                    print(f"      {i}. {sug}")
    
    # Test Case 2: Moderately bad - Should get 2 points
    print("\n\n" + "=" * 70)
    print("Test Case 2: 中等糟糕（應得 2 分）")
    print("=" * 70)
    
    moderate_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 1,
            "question_text": "在 Transformer 架構中，Multi-Head Attention 的主要優勢為何？",
            "options": {
                "A": "增加模型參數量",
                "B": "允許模型關注不同位置的資訊",
                "C": "減少訓練時間",
                "D": "自動進行特徵工程"
            },
            "correct_answer": "B",
            "source": {
                "page_number": "1",
                "evidence": "Multi-Head Attention 是 Transformer 的核心機制。"
            }
        }]
    }
    
    result2 = await critic.evaluate(moderate_case, criteria=["Understandable"])
    
    print(f"\n評估結果:")
    if "evaluations" in result2:
        for eval_item in result2["evaluations"]:
            print(f"\n📊 {eval_item['criteria']}")
            print(f"   評分: {eval_item['rating']}/5")
            print(f"   分析: {eval_item['analysis'][:200]}...")
    
    # Test Case 3: EXCELLENT (4 points standard) - Clear context + proper terminology
    print("\n\n" + "=" * 70)
    print("Test Case 3: 優秀標準（應得 4 分）")
    print("=" * 70)
    
    excellent_case = {
        "type": "multiple_choice",
        "questions": [{
            "question_number": 1,
            "question_text": """在機器學習中，我們常需要將資料分成「訓練集」和「測試集」。
訓練集用來讓模型學習規律，測試集則用來檢驗模型對「從未見過的資料」的預測能力。

例如：若要建立房價預測模型，我們可能用 80% 的房屋資料來訓練，剩下 20% 用來測試模型是否能準確預測新房屋的價格。

關於測試集的使用，下列何者正確？""",
            "options": {
                "A": "測試集的資料可以同時用於訓練，以提升準確度",
                "B": "測試集用於評估模型對未見過資料的預測能力",
                "C": "測試集必須與訓練集完全相同",
                "D": "測試集只在模型訓練過程中使用一次"
            },
            "correct_answer": "B",
            "source": {
                "page_number": "1",
                "evidence": "資料分割是監督式學習的基本步驟。"
            }
        }]
    }
    
    result3 = await critic.evaluate(excellent_case, criteria=["Understandable"])
    
    print(f"\n評估結果:")
    if "evaluations" in result3:
        for eval_item in result3["evaluations"]:
            print(f"\n📊 {eval_item['criteria']}")
            print(f"   評分: {eval_item['rating']}/5")
            print(f"   分析: {eval_item['analysis'][:200]}...")
    
    print("\n" + "=" * 70)
    print("📊 評分總結")
    print("=" * 70)
    if "evaluations" in result1:
        print(f"  Case 1 (真正糟糕): {result1['evaluations'][0]['rating']}/5 - 預期 1 分")
    if "evaluations" in result2:
        print(f"  Case 2 (中等糟糕): {result2['evaluations'][0]['rating']}/5 - 預期 2 分")
    if "evaluations" in result3:
        print(f"  Case 3 (優秀標準): {result3['evaluations'][0]['rating']}/5 - 預期 4 分")

if __name__ == "__main__":
    asyncio.run(test_extreme_cases())
