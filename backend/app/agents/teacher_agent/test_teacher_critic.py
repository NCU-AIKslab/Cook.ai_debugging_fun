import sys
import asyncio
from unittest.mock import MagicMock

# Mock db_logger BEFORE importing graph to avoid DB dependency issues during test
def mock_log_task_decorator(*args, **kwargs):
    def decorator(func):
        def wrapper(*f_args, **f_kwargs):
            # Inject dummy task ID into state (assuming state is the first arg)
            if f_args and isinstance(f_args[0], dict):
                f_args[0]["current_task_id"] = 999
            return func(*f_args, **f_kwargs)
        return wrapper
    return decorator

mock_logger = MagicMock()
mock_logger.log_task = mock_log_task_decorator
mock_logger.update_job_status = MagicMock()
mock_logger.save_generated_content = MagicMock(return_value="mock_content_id")
mock_logger.update_job_final_output = MagicMock()
mock_logger.get_job_status = MagicMock(return_value="running")

sys.modules["backend.app.utils.db_logger"] = mock_logger
sys.modules["backend.app.utils"] = MagicMock()
sys.modules["backend.app.utils"].db_logger = mock_logger

# Mock rag_agent to avoid actual vector search failure
mock_rag_agent = MagicMock()
mock_rag_agent.search.return_value = {
    "text_chunks": ["光合作用是植物利用光能將二氧化碳和水轉化為葡萄糖和氧氣的過程。", "光合作用主要發生在葉綠體中。", "光反應需要光，暗反應（卡爾文循環）不需要光。"],
    "page_content": [{"type": "structured_page_content", "page_number": 1, "content": [{"type": "text", "content": "光合作用是植物利用光能將二氧化碳和水轉化為葡萄糖和氧氣的過程。光合作用主要發生在葉綠體中。光反應需要光，暗反應（卡爾文循環）不需要光。"}]}]
}
sys.modules["backend.app.agents.rag_agent"] = MagicMock()
sys.modules["backend.app.agents.rag_agent"].rag_agent = mock_rag_agent

from dotenv import load_dotenv
from backend.app.agents.teacher_agent.graph import app

# Load env vars
load_dotenv()

async def test_critic_workflow():
    print("--- Starting Teacher Agent Critic Workflow Test ---")
    
    # Mock inputs
    inputs = {
        "job_id": 12345, 
        "user_query": "幫我生成1題選擇題",
        "unique_content_id": 45, 
        "workflow_mode": "quality_critic", 
        "max_iterations": 2
    }
    
    print(f"Inputs: {inputs}")
    
    try:
        # Run the graph
        # Note: The graph is synchronous or async? 
        # LangGraph apps are usually runnable via invoke (sync) or ainvoke (async).
        # The nodes are defined as sync functions in graph.py, but some might be async?
        # QualityCritic.evaluate is async.
        # But quality_critic_node in graph.py is defined as async def?
        # Let's check graph.py...
        # In critics/graph.py, quality_critic_node IS async.
        # In teacher_agent/graph.py, critic_node is sync def?
        # Let's check teacher_agent/graph.py again.
        
        # If critic_node calls critic_app.invoke(), and critic_app has async nodes...
        # LangGraph handles async nodes in sync invoke by running event loop?
        # It's safer to use ainvoke if there are async nodes.
        
        final_state = await app.ainvoke(inputs)
        
        print("\n--- Test Finished ---")
        print(f"Final Node: {final_state.get('next_node')}")
        print(f"Iteration Count: {final_state.get('iteration_count')}")
        
        critic_feedback = final_state.get("critic_feedback", [])
        print(f"\nCritic Feedback History ({len(critic_feedback)} rounds):")
        for i, fb in enumerate(critic_feedback):
            print(f"Round {i+1}: Status={fb.get('overall_status')}")
            for item in fb.get('feedback_items', []):
                print(f"  - [{item.get('criteria')}] Score: {item.get('score')}")
                print(f"    Feedback: {item.get('feedback')}")
                
        final_content = final_state.get("final_generated_content")
        print(f"\nFinal Content Type: {type(final_content)}")
        # print(final_content)

    except Exception as e:
        print(f"\nTest Failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_critic_workflow())
