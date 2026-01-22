import sys
import asyncio
import json
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import Critic App
from backend.app.agents.teacher_agent.critics.graph import critic_app

async def test_critic_quality():
    """
    Standalone test for the Critic Agent's quality evaluation.
    Input: Generated exam content (from your backend API)
    Output: 8-dimensional quality scores + feedback
    """
    
    print("--- Critic Agent Quality Test ---\n")
    
    # Sample exam content (you can replace this with real API output)
    sample_exam_content = [
        {
            "type": "multiple_choice",
            "questions": [
                {
                    "question_number": 1,
                    "question_text": "PCA（主成分分析）的主要目的為何？",
                    "options": {
                        "A": "增加數據的維度",
                        "B": "降維以簡化數據",
                        "C": "同時處理多個數據源",
                        "D": "提高數據的準確性"
                    },
                    "correct_answer": "B",
                    "source": {
                        "page_number": "25",
                        "evidence": "PCA的主要用途是將數據降維到較少的主要成分，以簡化數據的分析。"
                    }
                }
            ]
        }
    ]
    
    # You can also load from a JSON file:
    # with open("path/to/your/exam_output.json", "r", encoding="utf-8") as f:
    #     sample_exam_content = json.load(f)
    
    # Prepare input for Critic
    critic_input = {
        "content": sample_exam_content,
        "workflow_mode": "quality_critic"  # Options: "quality_critic", "fact_critic", "dual_critic"
    }
    
    print(f"Input Content ({len(sample_exam_content)} items):")
    print(json.dumps(sample_exam_content, ensure_ascii=False, indent=2)[:500] + "...\n")
    
    try:
        # Run Critic
        print("Running Critic Agent...\n")
        final_critic_state = await critic_app.ainvoke(critic_input)
        
        # Extract results
        overall_status = final_critic_state.get("overall_status", "unknown")
        final_feedback = final_critic_state.get("final_feedback", [])
        quality_score = final_critic_state.get("quality_score", 0.0)
        
        print("=" * 60)
        print(f"Overall Status: {overall_status}")
        print(f"Average Quality Score: {quality_score:.2f}/5.0")
        print("=" * 60)
        
        if final_feedback:
            print(f"\n📊 Quality Evaluation Results ({len(final_feedback)} items):\n")
            for i, item in enumerate(final_feedback, 1):
                print(f"[{i}] Question Index: {item.get('question_index')}")
                print(f"    Criterion: {item.get('criteria')}")
                print(f"    Score: {item.get('score')}/5.0")
                print(f"    Feedback:")
                for fb in item.get('feedback', []):
                    print(f"      - {fb}")
                print()
        else:
            print("\n✅ No issues found. All criteria passed!")
        
        # Print raw state for debugging
        print("\n--- Raw Critic State (for debugging) ---")
        print(json.dumps(final_critic_state, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"\n❌ Test Failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_critic_quality())
