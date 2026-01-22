"""
Teacher Testing Router: 處理教師端開發測試功能

此 router 僅包含開發測試用的端點，不包含生產環境使用的功能。
包含：
1. Critic 工作流程 E2E 測試 (test_critic_workflow)
2. RAG 檢索測試 (test_rag_retrieval)
3. RAG 完整流程測試 (test_rag_full_pipeline)
"""
import os
import time
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.utils import db_logger
from backend.app.agents.rag_agent import rag_agent
from backend.app.agents.teacher_agent.skills.exam_generator.exam_nodes import (
    _prepare_multimodal_content,
    get_llm
)
from langchain_core.messages import HumanMessage, SystemMessage

# Create router
router = APIRouter(prefix="/api/v1/testing", tags=["Teacher Development & Testing"])

# --- Pydantic Models ---

class TestCriticWorkflowRequest(BaseModel):
    """Request for testing the full critic workflow.
    
    Required Parameters:
        unique_content_id: 教材內容的唯一ID
        prompt: 教師的查詢指令（例如："生成5題選擇題關於機器學習"）
    
    Optional Parameters:
        user_id: 使用者ID，預設為 1
        enabled_critics: 啟用的critic類型列表，可選值：
            - [] : Workflow 1 (無critic評估，直接輸出)
            - ["fact"] : Workflow 2 (只用Ragas事實性指標)
            - ["quality"] : Workflow 3 (只用G-eval品質指標) [預設]
            - ["fact", "quality"] : Workflow 4 (兩者皆用)
        critic_mode: Critic評估模式，可選值：
            - "quick" : 快速模式（只評估整體，節省成本） [預設]
            - "comprehensive" : 完整模式（逐題評估 + 統計數據）
        max_iterations: 最大迭代次數，預設為 3
    """
    unique_content_id: int
    prompt: str
    user_id: int = 1
    enabled_critics: list[str] = ["quality"]
    critic_mode: str = "quick"
    max_iterations: int = 3

class TestRAGRequest(BaseModel):
    """Request for RAG debug endpoints"""
    unique_content_id: int
    query: str
    top_k: Optional[int] = 3
    user_id: int = 1

class TestRAGRetrievalResponse(BaseModel):
    """Response for /test_rag_retrieval"""
    query: str
    retrieval_results: Dict[str, Any]
    statistics: Dict[str, Any]

class TestRAGFullPipelineResponse(BaseModel):
    """Response for /test_rag_full_pipeline"""
    query: str
    retrieval_results: Dict[str, Any]
    generation_result: Dict[str, Any]
    evaluation_results: Dict[str, Any]  # Changed from ragas_preparation
    statistics: Dict[str, Any]


# --- Testing Endpoints ---

@router.post("/test_critic_workflow")
async def test_critic_workflow(request: TestCriticWorkflowRequest):
    """
    **Test API**: Multi-Critic 工作流程完整測試
    
    **執行流程**:
    1. 建立 job → 2. Router 路由 → 3. Generator 生成 → 4. Critics 評估 → 5. 聚合輸出
    
    **可用參數**:
    - `unique_content_id` (必填): 教材內容 ID
    - `prompt` (必填): 教師查詢指令
    - `user_id` (選填): 預設 1
    - `enabled_critics` (選填): 預設 ["quality"]
      - [] : Workflow 1 (無評估)
      - ["fact"] : Workflow 2 (Ragas 指標)
      - ["quality"] : Workflow 3 (G-eval 指標) [預設]
      - ["fact", "quality"] : Workflow 4 (全部)
    - `critic_mode` (選填): "quick" (預設) 或 "comprehensive"
    - `max_iterations` (選填): 預設 3
    """
    logging.basicConfig(level=logging.INFO)
    
    print(f"\n{'='*80}")
    print(f"[TEST CRITIC WORKFLOW] Starting new workflow")
    print(f"  - Prompt: {request.prompt[:50]}...")
    print(f"  - Content ID: {request.unique_content_id}")
    print(f"  - Enabled Critics: {request.enabled_critics}")
    print(f"  - Critic Mode: {request.critic_mode}")
    print(f"  - Max Iterations: {request.max_iterations}")
    print(f"{'='*80}\n")
    
    try:
        from backend.app.agents.teacher_agent.graph import app as teacher_app
        
        # Determine workflow_type for database
        if not request.enabled_critics:
            workflow_type = "1_no_critic"
        elif request.enabled_critics == ["fact"]:
            workflow_type = "2_fact_only"
        elif request.enabled_critics == ["quality"]:
            workflow_type = "3_qual_only"
        elif set(request.enabled_critics) == {"fact", "quality"}:
            workflow_type = "4_all_critics"
        else:
            workflow_type = "custom"
        
        # Create experiment config
        experiment_config = {
            "enabled_critics": request.enabled_critics,
            "critic_mode": request.critic_mode,
            "max_iterations": request.max_iterations
        }
        
        # Create job
        job_id = db_logger.create_job(
            user_id=request.user_id,
            input_prompt=request.prompt,
            workflow_type=workflow_type,
            experiment_config=experiment_config
        )
        
        if not job_id:
            raise HTTPException(status_code=500, detail="Failed to create job in database.")
        
        print(f"[TEST] Created job_id: {job_id}")
        
        # Prepare state for teacher agent
        initial_state = {
            "job_id": job_id,
            "user_id": request.user_id,
            "unique_content_id": request.unique_content_id,
            "user_query": request.prompt,
            "task_name": "auto_detected",
            "task_parameters": {},
            "final_result": None,
            "error": None,
            "next_node": None,
            "parent_task_id": None,
            "current_task_id": None,
            "iteration_count": 1,
            "max_iterations": request.max_iterations,
            # Multi-critic 參數
            "enabled_critics": request.enabled_critics,
            "critic_mode": request.critic_mode,
            "critic_feedback": [],
            "critic_passed": None,
            "critic_metrics": None,
            "final_generated_content": None
        }
        
        # Run the graph (async version since we have async nodes)
        print(f"\n[TEST] Invoking teacher agent graph...")
        final_state = await teacher_app.ainvoke(
            initial_state,
            config={"recursion_limit": 100}  # Increased from default 25 to avoid recursion errors
        )
        
        if final_state.get("error"):
            error_message = final_state.get("error")
            print(f"\n[TEST] Workflow failed: {error_message}\n")
            raise HTTPException(status_code=500, detail=error_message)
        
        # Extract critic results (always present in some form)
        fact_feedback = final_state.get("fact_feedback")
        fact_metrics = final_state.get("fact_metrics")
        fact_passed = final_state.get("fact_passed")
        
        quality_feedback = final_state.get("quality_feedback")
        quality_metrics = final_state.get("quality_metrics")
        quality_passed = final_state.get("quality_passed")
        
        # Calculate overall critic status from individual results
        # (critic_passed is only set in run_critics_node, not in separate nodes)
        enabled_critics = request.enabled_critics
        critics_results = []
        if "fact" in enabled_critics and fact_passed is not None:
            critics_results.append(fact_passed)
        if "quality" in enabled_critics and quality_passed is not None:
            critics_results.append(quality_passed)
        
        # All enabled critics must pass
        overall_passed = all(critics_results) if critics_results else None
        
        logging.info(f"[TEST CRITIC WORKFLOW] Completed - Job: {job_id}, Passed: {overall_passed}")
        
        # Return critic evaluation results (not the generated questions)
        response = {
            "job_id": job_id,
            "status": "completed",
            "workflow_type": workflow_type,
            "critic_evaluation": {
                "overall_passed": overall_passed,
                "fact_critic": {
                    "passed": fact_passed,
                    "feedback": fact_feedback,
                    "metrics": fact_metrics
                } if fact_feedback is not None else None,
                "quality_critic": {
                    "passed": quality_passed,
                    "feedback": quality_feedback,
                    "metrics": quality_metrics
                } if quality_feedback is not None else None
            },
            "message": "Workflow completed. Critic evaluation results are above. Generated questions are saved in database."
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        if 'job_id' in locals():
            db_logger.update_job_status(job_id, 'failed', error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Workflow failed: {str(e)}")

@router.post("/test_rag_retrieval", response_model=TestRAGRetrievalResponse)
async def test_rag_retrieval(request: TestRAGRequest):
    """
    **Test API**: RAG 檢索流程測試
    
    測試 RAG 檢索並返回原始數據，用於驗證：
    - Vision LLM 描述是否出現在 chunks
    - multimodal_metadata 是否正確
    - LLM 會接收到的 base64 圖片
    """
    try:
        retrieval_start = time.perf_counter()
        rag_result = rag_agent.search(
            user_prompt=request.query,
            unique_content_id=request.unique_content_id,
            top_k=request.top_k
        )
        retrieval_time = int((time.perf_counter() - retrieval_start) * 1000)
        
        llm_text, llm_images = _prepare_multimodal_content(rag_result["page_content"])
        chunks = rag_result.get("text_chunks", [])
        human_contexts = [chunk["text"] for chunk in chunks]
        total_images_in_chunks = sum(
            len(c.get("multimodal_metadata", {}).get("images", []))
            for c in chunks
        )
        
        return {
            "query": request.query,
            "retrieval_results": {
                "chunks": chunks,
                "page_content": rag_result["page_content"],
                "llm_input": {
                    "text": llm_text,
                    "images": llm_images,
                    "image_count": len(llm_images)
                },
                "human_readable_context": {
                    "chunks": human_contexts,
                    "combined": "\n\n---\n\n".join(human_contexts)
                }
            },
            "statistics": {
                "retrieval_time_ms": retrieval_time,
                "chunks_count": len(chunks),
                "pages_retrieved": len(rag_result["page_content"]),
                "total_images_in_chunks": total_images_in_chunks,
                "total_images_for_llm": len(llm_images)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG retrieval test failed: {str(e)}")

@router.post("/test_rag_full_pipeline", response_model=TestRAGFullPipelineResponse)
async def test_rag_full_pipeline(request: TestRAGRequest):
    """
    **Test API**: 完整 RAG 流程測試（檢索 + 生成 + Ragas 評估）
    
    測試完整流程並驗證：
    - LLM 是否使用圖片生成答案
    - Ragas 只接收純文字
    - 完整流程的執行時間
    - Ragas Faithfulness 分數
    - TaskSatisfaction 分數（任務符合度）
    """
    from backend.app.agents.teacher_agent.critics.fact_critic import (
        CustomFaithfulness,
        TaskSatisfaction,
        get_fact_critic_llm
    )
    
    try:
        # Step 1: Retrieval
        retrieval_start = time.perf_counter()
        rag_result = rag_agent.search(
            user_prompt=request.query,
            unique_content_id=request.unique_content_id,
            top_k=request.top_k
        )
        retrieval_time = int((time.perf_counter() - retrieval_start) * 1000)
        chunks = rag_result.get("text_chunks", [])
        
        # Step 2: Generation
        generation_start = time.perf_counter()
        text_for_llm, images_for_llm = _prepare_multimodal_content(rag_result["page_content"])
        llm = get_llm()
        prompt = f"基於以下內容回答問題: {request.query}\n\n{text_for_llm}"
        
        message_content = [{"type": "text", "text": prompt}]
        for img_url in images_for_llm:
            message_content.append({
                "type": "image_url",
                "image_url": {"url": img_url, "detail": "low"}
            })
        
        response = llm.invoke([
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content=message_content)
        ])
        generated_answer = response.content
        generation_time = int((time.perf_counter() - generation_start) * 1000)
        
        # Step 3: Ragas Faithfulness Evaluation
        ragas_start = time.perf_counter()
        contexts_for_ragas = [chunk["text"] for chunk in chunks]
        
        # Prepare Ragas input
        ragas_row = {
            "user_input": request.query,
            "response": generated_answer,
            "retrieved_contexts": contexts_for_ragas
        }
        
        # Run Faithfulness metric
        faithfulness_metric = CustomFaithfulness(llm=get_fact_critic_llm())
        faithfulness_result = await faithfulness_metric.score_with_feedback(ragas_row)
        
        # Step 4: TaskSatisfaction Evaluation (auto-detect task type)
        task_satisfaction = TaskSatisfaction()
        task_result = await task_satisfaction.evaluate(
            user_query=request.query,
            generated_content=generated_answer,
            task_type="auto"  # Auto-detect based on query keywords
        )
        
        ragas_time = int((time.perf_counter() - ragas_start) * 1000)
        
        # Build human-readable chunks without base64 images
        readable_chunks = []
        for chunk in chunks:
            readable_chunk = {
                "text": chunk.get("text", ""),
                "chunk_id": chunk.get("chunk_id", ""),
                "source_pages": chunk.get("source_pages", []),
                "similarity_score": chunk.get("similarity_score", 0),
                "image_count": len(chunk.get("multimodal_metadata", {}).get("images", [])) if chunk.get("multimodal_metadata") else 0
            }
            readable_chunks.append(readable_chunk)
        
        # Extract combined_human_text from page_content for full human-readable contexts
        page_contents = rag_result.get("page_content", [])
        human_readable_pages = []
        for page in page_contents:
            page_num = page.get("page_number", "Unknown")
            human_text = page.get("combined_human_text", "")
            if human_text:
                human_readable_pages.append({
                    "page_number": page_num,
                    "text": human_text
                })
        
        return {
            "query": request.query,
            "retrieval_results": {
                "chunks": readable_chunks,
                "llm_input": {
                    "text": text_for_llm,  # Full text, no truncation
                    "image_count": len(images_for_llm),
                    "note": "base64 images omitted for readability"
                },
                "human_contexts": {
                    "from_chunks": contexts_for_ragas,  # Original chunk texts (may be truncated)
                    "from_pages": human_readable_pages  # Full page content with combined_human_text
                }
            },
            "generation_result": {
                "answer": generated_answer,  # Full answer, no truncation
                "used_images": len(images_for_llm) > 0,
                "model": llm.model_name
            },
            "evaluation_results": {
                "faithfulness": {
                    "raw_score": faithfulness_result["score"],
                    "normalized_score": faithfulness_result["normalized_score"],
                    "analysis": faithfulness_result["analysis"],
                    "suggestions": faithfulness_result["suggestions"]
                },
                "task_satisfaction": {
                    "task_type": task_result["task_type"],  # Detected task type
                    "raw_score": task_result["score"],
                    "normalized_score": task_result["normalized_score"],
                    "checks": task_result["checks"],
                    "weighted_score": task_result["weighted_score"],
                    "total_weight": task_result["total_weight"],
                    "analysis": task_result["analysis"],
                    "suggestions": task_result["suggestions"]
                }
            },
            "statistics": {
                "retrieval_time_ms": retrieval_time,
                "generation_time_ms": generation_time,
                "eval_time_ms": ragas_time,
                "total_time_ms": retrieval_time + generation_time + ragas_time,
                "chunks_retrieved": len(chunks),
                "pages_retrieved": len(page_contents),
                "images_sent_to_llm": len(images_for_llm)
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"RAG full pipeline test failed: {str(e)}")
