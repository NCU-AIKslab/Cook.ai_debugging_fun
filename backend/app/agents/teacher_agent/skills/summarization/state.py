from typing import List, Dict, Any, TypedDict, Optional

class SummarizationState(TypedDict):
    """
    Represents the state for the summarization skill.
    """
    job_id: str
    query: str
    unique_content_id: str
    retrieved_page_content: List[Dict[str, Any]]
    final_generated_content: Optional[Dict[str, Any]]
    error: Optional[str]
    
    # Fields for logging and graph flow
    parent_task_id: Optional[int]
    current_task_id: Optional[int]
    iteration_count: Optional[int]  # Track which iteration of refinement this is
