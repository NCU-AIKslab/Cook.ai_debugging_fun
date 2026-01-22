from typing import TypedDict, List, Dict, Any, Optional

class CriticState(TypedDict):
    """
    Represents the state of the Critic Agent sub-graph.
    """
    # Input
    content: Any  # The content to be evaluated (usually List[Dict])
    workflow_mode: str  # 'fact_critic', 'quality_critic', 'dual_critic'
    task_name: str  # 'exam_generation', 'summary', etc. (from router node)
    user_query: str  # Original user query
    
    # Intermediate results
    fact_score: Optional[float]
    quality_score: Optional[float]
    fact_feedback: List[Dict[str, Any]]
    quality_feedback: List[Dict[str, Any]]
    
    # Task satisfaction results
    faithfulness_score: Optional[float]
    task_satisfaction_score: Optional[float]
    task_satisfaction_checks: Optional[List[Dict[str, Any]]]
    
    # Output
    final_feedback: List[Dict[str, Any]]  # Aggregated feedback
    overall_status: str  # 'pass' or 'fail'

