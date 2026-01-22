
from typing import TypedDict, List, Dict, Any, Optional

class ExamGenerationState(TypedDict):
    """
    Represents the state of the exam generation graph.
    """
    job_id: int  # The ID of the parent orchestration job for logging
    query: str
    unique_content_id: int
    main_title: Optional[str] # Add this
    retrieved_text_chunks: List[Dict[str, Any]]
    retrieved_page_content: List[Dict[str, Any]]
    generation_plan: List[Dict[str, Any]]
    current_task: Optional[Dict[str, Any]]
    final_generated_content: List[str]
    generation_errors: List[Dict[str, Any]] # New field to store errors from individual generation tasks
    error: Optional[str]
    parent_task_id: Optional[int] # The ID of the parent task for hierarchical logging
    iteration_count: Optional[int]  # Track which iteration of refinement this is
