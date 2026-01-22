from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage
import logging

from .state import CriticState
from .quality_critic import QualityCritic
from backend.app.agents.teacher_agent.skills.exam_generator.exam_nodes import get_llm # Reuse LLM getter

logger = logging.getLogger(__name__)

# --- Nodes ---

async def fact_critic_node(state: CriticState) -> Dict[str, Any]:
    """
    Runs Ragas-based Faithfulness and rule-based TaskSatisfaction metrics.
    
    Metrics:
    - Faithfulness: 答案是否基於 context，沒有捏造
    - TaskSatisfaction: 生成結果是否符合任務要求（題數、題型、格式）
    """
    workflow_mode = state.get("workflow_mode", "generator_only")
    if workflow_mode not in ["fact_critic", "dual_critic"]:
        return {}
        
    content = state.get("content", [])
    user_query = state.get("user_query", "")
    task_name = state.get("task_name", "exam_generation")  # From router node
    
    feedback_items = []
    faithfulness_scores = []
    
    # Initialize metrics
    from .fact_critic import get_fact_critic_llm, CustomFaithfulness, TaskSatisfaction
    
    llm = get_fact_critic_llm()
    
    faithfulness_metric = CustomFaithfulness()
    faithfulness_metric.llm = llm
    
    task_satisfaction = TaskSatisfaction()
    
    # 1. Evaluate Faithfulness per question
    for item in content:
        questions_list = item.get("questions", [])
        
        for q in questions_list:
            question_text = q.get("question_text", "")
            correct_option = q.get("correct_answer", "")
            options = q.get("options", {})
            answer_text = options.get(correct_option, "")
            
            source = q.get("source", {})
            evidence = source.get("evidence", "")
            contexts = [evidence] if evidence else []
            
            row = {
                "user_input": question_text,
                "response": answer_text,
                "retrieved_contexts": contexts
            }
            
            if contexts:
                f_res = await faithfulness_metric.score_with_feedback(row)
                faithfulness_scores.append(f_res["normalized_score"])
                
                if f_res.get("suggestions"):
                    feedback_items.append({
                        "question_index": content.index(item),
                        "type": "faithfulness",
                        "score": f_res["normalized_score"],
                        "analysis": f_res.get("analysis", ""),
                        "suggestions": f_res.get("suggestions", [])
                    })
    
    # 2. Evaluate TaskSatisfaction using task_name from state
    task_result = await task_satisfaction.evaluate(
        user_query=user_query,
        generated_content=content,
        task_type=task_name  # Use task_name from state (set by router node)
    )
    
    # Collect task satisfaction feedback if not perfect
    if task_result["normalized_score"] < 5:
        feedback_items.append({
            "question_index": -1,  # Overall assessment
            "type": "task_satisfaction",
            "score": task_result["normalized_score"],
            "checks": task_result["checks"],
            "analysis": task_result["analysis"],
            "suggestions": task_result["suggestions"]
        })
    
    # Calculate combined fact score (average of Faithfulness and TaskSatisfaction)
    avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 5.0
    combined_score = (avg_faithfulness + task_result["normalized_score"]) / 2
    
    return {
        "fact_score": combined_score,
        "faithfulness_score": avg_faithfulness,
        "task_satisfaction_score": task_result["normalized_score"],
        "task_satisfaction_checks": task_result["checks"],
        "fact_feedback": feedback_items
    }

async def quality_critic_node(state: CriticState) -> Dict[str, Any]:
    """
    Runs G-Eval based quality checking with LLM-generated improvement suggestions.
    """
    workflow_mode = state.get("workflow_mode", "generator_only")
    if workflow_mode not in ["quality_critic", "dual_critic"]:
        return {}
        
    content = state.get("content", [])
    llm = get_llm()
    critic = QualityCritic(llm, threshold=4.0)
    
    feedback_items = []
    total_score = 0.0
    count = 0
    
    for item in content:
        # Evaluate using G-Eval framework
        result = await critic.evaluate(item, criteria=None)
        
        if "evaluations" in result:
            for eval_item in result["evaluations"]:
                score = eval_item.get("rating", 0)
                total_score += score
                count += 1
                
                # Only create feedback for low scores (< threshold)
                # Now we have LLM-generated suggestions!
                suggestions = eval_item.get("suggestions", [])
                if suggestions:  # If LLM provided suggestions
                    feedback_items.append({
                        "question_index": content.index(item),
                        "type": "quality",
                        "criteria": eval_item.get("criteria"),
                        "score": score,
                        "analysis": eval_item.get("analysis", ""),
                        "suggestions": suggestions  # LLM-generated improvement suggestions
                    })
        elif "error" in result:
            # Handle evaluation error
            logger.error(f"Quality evaluation failed: {result['error']}")
            
    avg_score = total_score / count if count > 0 else 5.0 # Default to max if empty
    
    return {
        "quality_score": avg_score,
        "quality_feedback": feedback_items
    }

def aggregate_feedback_node(state: CriticState) -> Dict[str, Any]:
    """
    Aggregates feedback from all critics.
    """
    fact_feedback = state.get("fact_feedback", [])
    quality_feedback = state.get("quality_feedback", [])
    
    all_feedback = fact_feedback + quality_feedback
    
    # Determine overall status
    # If any critical feedback exists, fail.
    # Or use a score threshold.
    
    # Strategy: If any item has a score below threshold, Fail.
    # Fact threshold: 1.0 (Strict)
    # Quality threshold: 4.0
    
    status = "pass"
    if all_feedback:
        status = "fail"
        
    return {
        "final_feedback": all_feedback,
        "overall_status": status
    }

# --- Graph ---

critic_workflow = StateGraph(CriticState)

critic_workflow.add_node("fact_critic", fact_critic_node)
critic_workflow.add_node("quality_critic", quality_critic_node)
critic_workflow.add_node("aggregate_feedback", aggregate_feedback_node)

# Parallel execution
critic_workflow.set_entry_point("fact_critic") # Start with Fact
critic_workflow.add_edge("fact_critic", "quality_critic") # Currently sequential for simplicity in LangGraph 
# To do parallel: 
# critic_workflow.set_entry_point("start_node")
# critic_workflow.add_edge("start_node", "fact_critic")
# critic_workflow.add_edge("start_node", "quality_critic")
# But we need a start node. 
# For now, sequential is fine: Fact -> Quality -> Aggregate.
# Or better: use a fan-out pattern if latency is critical. 
# Given the async nature, sequential nodes with async calls inside are still blocking.
# Let's keep it simple: Fact -> Quality -> Aggregate.

critic_workflow.add_edge("quality_critic", "aggregate_feedback")
critic_workflow.add_edge("aggregate_feedback", END)

critic_app = critic_workflow.compile()
