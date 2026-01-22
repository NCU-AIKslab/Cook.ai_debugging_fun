from typing import TypedDict, Dict, Any, Optional, List

class TeacherAgentState(TypedDict):
    """
    Represents the state for the main Teacher Agent.
    This state is passed down to the skill-specific sub-graphs.
    """
    # Core identifiers
    job_id: int
    user_id: int
    unique_content_id: int
    
    # User's request
    user_query: str
    
    # Parsed task from a higher-level router (or can be parsed here)
    # For now, we assume the task is 'exam_generation'
    task_name: str
    task_parameters: Dict[str, Any]

    # Final result from the skill sub-graph
    final_result: Any
    error: Optional[str]
    
    # For routing logic
    next_node: Optional[str]
    parent_task_id: Optional[int]
    current_task_id: Optional[int]

    # === Critic 配置 ===
    enabled_critics: List[str]  # ["fact", "quality"] - 用戶可選擇啟用哪些 critic
    critic_mode: str  # "quick" or "comprehensive"
    
    # === 迭代管理 ===
    iteration_count: int  # 當前迭代次數 (預設 1)
    max_iterations: int  # 最大迭代次數 (預設 3)
    
    # === Critic Feedback (統一格式) ===
    # Critic results (now separate for each critic)
    fact_passed: Optional[bool] # Fact critic passed
    fact_feedback: Optional[Dict[str, Any]] # Fact critic feedback
    fact_metrics: Optional[Dict[str, Any]] # Fact critic metrics
    fact_failed_criteria: Optional[List[str]] # Fact critic failed criteria
    
    quality_passed: Optional[bool] # Quality critic passed
    quality_feedback: Optional[Dict[str, Any]] # Quality critic feedback
    quality_metrics: Optional[Dict[str, Any]] # Quality critic metrics
    quality_failed_criteria: Optional[List[str]] # Quality critic failed criteria
    
    # Legacy fields (kept for backward compatibility)
    critic_passed: Optional[bool]  # Deprecated: use fact_passed and quality_passed
    critic_feedback: Optional[List[Dict]]  # Deprecated
    critic_metrics: Optional[Dict]  # Deprecated
    
    # === 版本追蹤 ===
    generation_history: List[Dict]  # 每個版本的生成內容
    
    # === RAG 快取 ===
    rag_cache: Optional[Dict]  # 快取 RAG 檢索結果，避免重複檢索
    retrieved_text_chunks: Optional[List[Dict]]  # RAG 檢索到的 text chunks，供 fact_critic 使用
    
    # === Legacy fields (for backward compat) ===
    workflow_mode: str  # 'generator_only', 'fact_critic', 'quality_critic', 'dual_critic'
    final_generated_content: Any  # Standardized output from skills for evaluation
