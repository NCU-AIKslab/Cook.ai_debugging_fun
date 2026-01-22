"""
Teacher Agent Router: 處理教師端 Agent 互動與 Critic 評估功能

此 router 包含：
1. Agent 對話互動 (chat_with_agent)
2. Critic 評估功能 (evaluate_by_job) - 因為 Critic 是 Agent 互動流程的一部分
"""
from typing import Any
import json
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.app.agents.teacher_agent.graph import app as teacher_agent_app
from backend.app.utils import db_logger

# Create router
router = APIRouter(prefix="/api/v1", tags=["Teacher Agent Interaction"])

# --- Pydantic Models ---

# Critic workflow mapping
CRITIC_WORKFLOW_MAP = {
    1: [],                    # no_critic
    2: ["fact"],              # fact_only
    3: ["quality"],           # quality_only
    4: ["fact", "quality"]    # fact_then_quality
}

class ChatRequest(BaseModel):
    """Request model for chat with optional critic workflow."""
    unique_content_id: int
    prompt: str
    user_id: int = 1
    critic_workflow: int = Field(4, ge=1, le=4, description="1=no_critic, 2=fact_only, 3=quality_only, 4=fact_then_quality")
    mode: str = Field("quick", description="Evaluation mode: 'quick' or 'comprehensive'")
    max_iterations: int = Field(3, ge=1, le=5, description="Max refinement iterations")

class ChatResponse(BaseModel):
    job_id: int
    result: Any

class EvaluateRequest(BaseModel):
    """Request model for standalone evaluation."""
    job_id: int = Field(..., description="Job ID to evaluate")
    critic_workflow: int = Field(4, ge=2, le=4, description="2=fact_only, 3=quality_only, 4=fact_then_quality")
    mode: str = Field("quick", description="Evaluation mode: 'quick' or 'comprehensive'")


# --- Agent Interaction Endpoint ---

@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """
    Main endpoint for interacting with the Teacher Agent.
    
    critic_workflow options:
    - 1: no_critic (generate only)
    - 2: fact_only (Faithfulness + TaskSatisfaction)
    - 3: quality_only (G-Eval)
    - 4: fact_then_quality (Fact must pass before Quality)
    """
    # Map workflow number to enabled_critics list
    enabled_critics = CRITIC_WORKFLOW_MAP.get(request.critic_workflow, ["fact", "quality"])
    
    # Determine workflow_type for DB logging
    workflow_type_map = {
        1: "1_no_critic",
        2: "2_fact_only", 
        3: "3_quality_only",
        4: "4_fact_then_quality"
    }
    workflow_type = workflow_type_map.get(request.critic_workflow, "agent_chat")
    
    job_id = db_logger.create_job(
        user_id=request.user_id,
        input_prompt=request.prompt,
        workflow_type=workflow_type
    )
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create a chat job.")

    # Input for the teacher_agent graph
    inputs = {
        "job_id": job_id,
        "user_id": request.user_id,
        "user_query": request.prompt,
        "unique_content_id": request.unique_content_id,
        # Critic configuration
        "enabled_critics": enabled_critics,
        "critic_mode": request.mode,
        "max_iterations": request.max_iterations,
    }

    try:
        final_state = await teacher_agent_app.ainvoke(inputs)

        if final_state.get('error'):
            error_message = f"Generation failed: {final_state.get('error')}"
            db_logger.update_job_status(job_id, 'failed', error_message=error_message)
            raise HTTPException(status_code=500, detail=error_message)
        else:
            api_response_payload = final_state.get("final_result")

            if not isinstance(api_response_payload, dict):
                 raise HTTPException(status_code=500, detail="Final result payload structure missing or invalid.")

            json_serializable_content = json.loads(json.dumps(api_response_payload, ensure_ascii=False))
            
            if 'job_id' in json_serializable_content:
                del json_serializable_content['job_id']
            
            # Extract critic evaluation results if critics were enabled
            critic_evaluation = None
            if enabled_critics:
                fact_passed = final_state.get("fact_passed")
                quality_passed = final_state.get("quality_passed")
                
                # Calculate overall based on enabled critics
                results = []
                if "fact" in enabled_critics and fact_passed is not None:
                    results.append(fact_passed)
                if "quality" in enabled_critics and quality_passed is not None:
                    results.append(quality_passed)
                
                critic_evaluation = {
                    "critic_workflow": request.critic_workflow,
                    "overall_passed": all(results) if results else None,
                    "iteration_count": final_state.get("iteration_count", 1),
                    "fact_critic": {
                        "passed": fact_passed,
                        "feedback": final_state.get("fact_feedback"),
                        "metrics": final_state.get("fact_metrics")
                    } if "fact" in enabled_critics else None,
                    "quality_critic": {
                        "passed": quality_passed,
                        "feedback": final_state.get("quality_feedback"),
                        "metrics": final_state.get("quality_metrics")
                    } if "quality" in enabled_critics else None
                }
            
            # Build full response
            full_result = json_serializable_content
            if critic_evaluation:
                full_result["evaluation"] = critic_evaluation
            
            return ChatResponse(
                job_id=job_id,
                result=full_result
            )
    except Exception as e:
        db_logger.update_job_status(job_id, 'failed', error_message=str(e))
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# --- Standalone Evaluation Endpoint ---

@router.post("/evaluate")
async def evaluate_endpoint(request: EvaluateRequest):
    """
    Standalone evaluation endpoint for re-evaluating generated content.
    
    critic_workflow options (2-4 only):
    - 2: fact_only (Faithfulness + TaskSatisfaction)
    - 3: quality_only (G-Eval)
    - 4: fact_then_quality (Fact must pass before Quality)
    
    Returns structured evaluation results with database logging.
    """
    import logging
    start_time = time.time()
    
    try:
        from backend.app.agents.teacher_agent.critics.quality_critic import QualityCritic
        from backend.app.agents.teacher_agent.critics.fact_critic import (
            CustomFaithfulness, TaskSatisfaction, get_fact_critic_llm
        )
        from backend.app.agents.teacher_agent.skills.exam_generator.exam_nodes import get_llm
        from backend.app.agents.teacher_agent.critics.critic_db_utils import (
            get_generated_content_by_job_id,
            get_rag_chunks_by_job_id,
            save_evaluation_to_db
        )
        
        # Map workflow to enabled critics
        enabled_critics = CRITIC_WORKFLOW_MAP.get(request.critic_workflow, ["fact", "quality"])
        
        # Step 1: Get generated content
        content_data = get_generated_content_by_job_id(request.job_id)
        if not content_data:
            raise HTTPException(status_code=404, detail=f"No content found for job_id {request.job_id}")
        
        content = content_data["content"]
        display_type = content.get("display_type", "unknown")
        
        # Step 2: Get RAG context
        rag_chunks = get_rag_chunks_by_job_id(request.job_id, limit=10)
        contexts = []
        if rag_chunks:
            contexts = [c['chunk_text'] for c in rag_chunks]
        
        # Determine task type from display_type
        task_type_map = {
            "exam_questions": "exam_generation",
            "summary_report": "summary"
        }
        task_type = task_type_map.get(display_type, "generic")
        
        # Prepare content for evaluation
        generated_content = content.get("content", content)
        user_query = content_data.get("user_query", "")
        
        # Initialize results
        fact_result = None
        quality_result = None
        overall_passed = True
        
        # Step 3: Run Fact Critic (if enabled)
        if "fact" in enabled_critics:
            logging.info(f"📐 Running Fact Critic for job {request.job_id}")
            
            # Faithfulness
            faithfulness_metric = CustomFaithfulness(llm=get_fact_critic_llm())
            eval_data = {
                "user_input": user_query,
                "response": json.dumps(generated_content, ensure_ascii=False),
                "retrieved_contexts": contexts
            }
            faithfulness_res = await faithfulness_metric.score_with_feedback(eval_data)
            
            # TaskSatisfaction
            task_satisfaction = TaskSatisfaction()
            task_res = await task_satisfaction.evaluate(
                user_query=user_query,
                generated_content=generated_content,
                task_type=task_type
            )
            
            THRESHOLD = 4
            fact_passed = (faithfulness_res["normalized_score"] >= THRESHOLD and 
                          task_res["normalized_score"] >= THRESHOLD)
            
            fact_result = {
                "passed": fact_passed,
                "faithfulness": {
                    "score": faithfulness_res["normalized_score"],
                    "raw_score": faithfulness_res["score"],
                    "analysis": faithfulness_res["analysis"],
                    "suggestions": faithfulness_res["suggestions"]
                },
                "task_satisfaction": {
                    "score": task_res["normalized_score"],
                    "task_type": task_res.get("task_type", task_type),
                    "checks": task_res["checks"],
                    "analysis": task_res["analysis"],
                    "suggestions": task_res["suggestions"]
                }
            }
            
            if not fact_passed:
                overall_passed = False
                # If workflow 4 and fact failed, skip quality
                if request.critic_workflow == 4:
                    logging.info(f"❌ Fact Critic failed, skipping Quality Critic (workflow 4)")
        
        # Step 4: Run Quality Critic (if enabled and conditions met)
        should_run_quality = "quality" in enabled_critics
        if request.critic_workflow == 4 and fact_result and not fact_result["passed"]:
            should_run_quality = False  # Skip quality if fact failed in workflow 4
        
        if should_run_quality:
            logging.info(f"✨ Running Quality Critic for job {request.job_id}")
            
            llm = get_llm()
            critic = QualityCritic(llm=llm, threshold=4.0)
            
            # Parse content for quality evaluation
            if display_type == "exam_questions":
                all_questions = []
                exam_data = content.get("content", [])
                if isinstance(exam_data, list):
                    for block in exam_data:
                        questions = block.get("questions", [])
                        for q in questions:
                            q["question_type"] = block.get("type", "unknown")
                        all_questions.extend(questions)
                
                exam = {"type": "exam", "questions": all_questions}
                rag_text = "\n\n".join(contexts) if contexts else None
                
                evaluation = await critic.evaluate_exam(
                    exam=exam,
                    rag_content=rag_text,
                    mode=request.mode
                )
                
                evaluations = evaluation.get("overall", {}).get("evaluations", [])
                quality_passed = all(e.get("rating", 0) >= 4.0 for e in evaluations)
                
            else:
                # Summary or generic content
                evaluation = await critic.evaluate(content=content, criteria=None)
                evaluations = evaluation.get("evaluations", [])
                quality_passed = all(e.get("rating", 0) >= 4.0 for e in evaluations)
            
            quality_result = {
                "passed": quality_passed,
                "evaluations": evaluations
            }
            
            if not quality_passed:
                overall_passed = False
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Step 5: Build response
        workflow_names = {2: "fact_only", 3: "quality_only", 4: "fact_then_quality"}
        
        response = {
            "job_id": request.job_id,
            "status": "completed",
            "critic_workflow": request.critic_workflow,
            "workflow_name": workflow_names.get(request.critic_workflow, "unknown"),
            "evaluation": {
                "overall_passed": overall_passed,
                "fact_critic": fact_result,
                "quality_critic": quality_result
            },
            "duration_ms": duration_ms
        }
        
        # Step 6: Save to database
        evaluation_mode = f"{workflow_names.get(request.critic_workflow)}_{request.mode}"
        
        save_result = save_evaluation_to_db(
            job_id=request.job_id,
            parent_task_id=content_data.get("source_agent_task_id"),
            evaluation_result=response["evaluation"],
            duration_ms=duration_ms,
            is_passed=overall_passed,
            feedback={"suggestions": []},  # TODO: aggregate suggestions
            metrics_detail={
                "fact_result": fact_result,
                "quality_result": quality_result,
                "overall_passed": overall_passed
            },
            evaluation_mode=evaluation_mode
        )
        
        if save_result:
            eval_task_id, task_eval_id = save_result
            response["saved"] = {
                "evaluation_task_id": eval_task_id,
                "task_evaluation_id": task_eval_id
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")

