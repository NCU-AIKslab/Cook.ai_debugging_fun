from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
from .state import ExamGenerationState
from backend.app.utils import db_logger # Import db_logger

load_dotenv()


# Import all the necessary nodes and the new router logic
from .exam_nodes import (
    retrieve_chunks_node,
    plan_generation_tasks_node,
    prepare_next_task_node, # New node for state modification
    should_continue_router, # New side-effect-free router
    generate_multiple_choice_node,
    generate_short_answer_node,
    generate_true_false_node,
    aggregate_final_output_node, # Import the new aggregation node
    handle_error_node,
)

# Create a new graph
workflow = StateGraph(ExamGenerationState)

# Add the nodes to the graph
workflow.add_node("retrieve_chunks", retrieve_chunks_node)
workflow.add_node("plan_generation_tasks", plan_generation_tasks_node)
workflow.add_node("prepare_next_task", prepare_next_task_node) # Add the new node
workflow.add_node("generate_multiple_choice", generate_multiple_choice_node)
workflow.add_node("generate_short_answer", generate_short_answer_node)
workflow.add_node("generate_true_false", generate_true_false_node)
workflow.add_node("aggregate_final_output", aggregate_final_output_node) # Add the new aggregation node
workflow.add_node("handle_error", handle_error_node)

# --- Define the new graph structure ---
workflow.set_entry_point("retrieve_chunks")
workflow.add_edge("retrieve_chunks", "plan_generation_tasks")

# After planning, move to the new preparation node, which is the entry point of the loop
workflow.add_edge("plan_generation_tasks", "prepare_next_task")

# The conditional edge now starts from the preparation node
workflow.add_conditional_edges(
    "prepare_next_task",
    should_continue_router,
    {
        "generate_multiple_choice": "generate_multiple_choice",
        "generate_short_answer": "generate_short_answer",
        "generate_true_false": "generate_true_false",
        "handle_error": "handle_error",
        "end": "aggregate_final_output" # Point to the aggregation node
    }
)

# After each generation task, loop back to the preparation node to get the next task
workflow.add_edge('generate_multiple_choice', 'prepare_next_task')
workflow.add_edge('generate_short_answer', 'prepare_next_task')
workflow.add_edge('generate_true_false', 'prepare_next_task')

# The aggregation node leads to the end
workflow.add_edge('aggregate_final_output', END)

# The error node leads to the end
workflow.add_edge('handle_error', END)

# Compile the graph into a runnable app
app = workflow.compile()

# Example of how to run the graph
if __name__ == '__main__':
    import os
    import json
    from backend.app.agents.teacher_agent.ingestion import process_file

    print("--- End-to-End Material Generator Test Runner (Plan-and-Execute) ---")
    
    # --- Step 1: Ingestion ---
    TEST_FILES_DIR = "test_files"
    if not os.path.isdir(TEST_FILES_DIR):
        print(f"Error: Test files directory not found at '{TEST_FILES_DIR}'.")
        exit()
    
    print("\nAvailable test files:")
    test_files = [f for f in os.listdir(TEST_FILES_DIR) if os.path.isfile(os.path.join(TEST_FILES_DIR, f))]
    for i, f in enumerate(test_files):
        print(f"  {i+1}: {f}")
    
    try:
        file_choice = int(input("Enter the number of the file to process: ")) - 1
        test_file_name = test_files[file_choice]
        test_file_path = os.path.join(TEST_FILES_DIR, test_file_name)
    except (ValueError, IndexError):
        print("Invalid choice.")
        exit()

    print(f"\nProcessing file: {test_file_path}...")
    unique_content_id = process_file(
        file_path=test_file_path,
        uploader_id=1, # Mock uploader
        course_id=1,   # Mock course
        force_reprocess=False
    )

    if not unique_content_id:
        print("\n--- Ingestion failed. Aborting test. ---")
        exit()
    
    print(f"\n--- Ingestion successful. Using unique_content_id: {unique_content_id} ---")

    # --- Step 2: Generation ---
    print("\nEnter your query (e.g., '出 3 題選擇題和 2 題是非題')")
    user_query = input("> ")

    inputs = {
        "query": user_query,
        "unique_content_id": unique_content_id,
        "question_type": "" # This is now deprecated, but the state still has it
    }

    print(f"\n--- Running generation graph for content ID: {unique_content_id} ---")

    try:
        final_state = app.invoke(inputs)

        print("\n--- Graph execution finished ---")
        
        print("\n--- Retrieved Text Chunks (for debugging) ---")
        text_chunks = final_state.get('retrieved_text_chunks', [])
        if not text_chunks:
            print("No text chunks were retrieved.")
        else:
            for i, chunk in enumerate(text_chunks):
                print(f"  Chunk {i+1}: '{chunk.get('text', '')[:100]}...'")
        print("---------------------------------------------")

        if final_state.get('error'):
            print(f"\nFinal state has an error: {final_state.get('error')}")
        else:
            print("\n--- Final Generated Content ---")
            final_content_parts = final_state.get("final_generated_content", [])
            # Join the parts for final display
            full_output = "\n\n".join(final_content_parts)
            print(full_output)
            print("-----------------------------\n")

    except Exception as e:
        print(f"\nAn exception occurred while running the graph: {e}")
        print("Please ensure your API keys are set correctly and the database is accessible.")