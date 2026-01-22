"""
Database utility functions for Quality Critic evaluation.
"""
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, insert, update
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import json
import logging

logger = logging.getLogger(__name__)

from backend.app.utils.db_logger import (
    engine, 
    orchestration_jobs, 
    generated_contents, 
    agent_tasks,
    agent_task_sources,
    TAIPEI_TZ
)

# Reflect document_chunks table
from sqlalchemy import Table, MetaData
metadata = MetaData()
try:
    document_chunks = Table('document_chunks', metadata, autoload_with=engine)
    task_evaluations = Table('task_evaluations', metadata, autoload_with=engine)
except Exception as e:
    logger.warning(f"Could not reflect tables: {e}")
    document_chunks = None
    task_evaluations = None


def get_generated_content_by_job_id(job_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve generated content and metadata by job_id.
    
    Returns:
        Dict containing:
        - content_id: int
        - content_type: str
        - content: dict
        - title: str
        - created_at: datetime
        - source_agent_task_id: int
        - user_id: int
        - input_prompt: str
    """
    try:
        with engine.connect() as conn:
            # Step 1: Get final_output_id from orchestration_jobs
            job_stmt = select(
                orchestration_jobs.c.final_output_id,
                orchestration_jobs.c.user_id,
                orchestration_jobs.c.input_prompt,
                orchestration_jobs.c.status
            ).where(orchestration_jobs.c.id == job_id)
            
            job_result = conn.execute(job_stmt).fetchone()
            
            if not job_result:
                logger.info(f"Job {job_id} not found")
                return None
            
            if job_result.status != 'completed':
                logger.info(f"Job {job_id} not completed (status: {job_result.status})")
                return None
            
            if not job_result.final_output_id:
                logger.info(f"Job {job_id} has no final_output_id")
                return None
            
            # Step 2: Get generated content
            content_stmt = select(
                generated_contents.c.id,
                generated_contents.c.content_type,
                generated_contents.c.content,
                generated_contents.c.title,
                generated_contents.c.created_at,
                generated_contents.c.source_agent_task_id
            ).where(generated_contents.c.id == job_result.final_output_id)
            
            content_result = conn.execute(content_stmt).fetchone()
            
            if not content_result:
                logger.info(f"Content {job_result.final_output_id} not found")
                return None
            
            return {
                "content_id": content_result.id,
                "content_type": content_result.content_type,
                "content": content_result.content,
                "title": content_result.title,
                "created_at": content_result.created_at,
                "source_agent_task_id": content_result.source_agent_task_id,
                "user_id": job_result.user_id,
                "input_prompt": job_result.input_prompt
            }
            
    except Exception as e:
        logger.error(f"ERROR retrieving content for job {job_id}: {e}")
        return None


def get_rag_chunks_by_task_id(task_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieve RAG chunks referenced by an agent task.
    
    Args:
        task_id: Agent task ID
        limit: Maximum number of chunks to retrieve
    
    Returns:
        List of dicts containing:
        - chunk_id: int
        - chunk_text: str
        - metadata: dict (contains page_number, etc.)
    """
    if document_chunks is None:
        logger.warning("document_chunks table not available")
        return []
    
    try:
        with engine.connect() as conn:
            # Import and_ for proper SQL and condition
            from sqlalchemy import and_
            
            # Join agent_task_sources with document_chunks
            stmt = select(
                document_chunks.c.id,
                document_chunks.c.chunk_text,
                document_chunks.c.metadata,
                document_chunks.c.chunk_order
            ).select_from(
                agent_task_sources.join(
                    document_chunks,
                    and_(
                        agent_task_sources.c.source_id == document_chunks.c.id,
                        agent_task_sources.c.source_type == 'chunk'
                    )
                )
            ).where(
                agent_task_sources.c.task_id == task_id
            ).order_by(
                document_chunks.c.chunk_order
            ).limit(limit)
            
            results = conn.execute(stmt).fetchall()
            
            chunks = [
                {
                    "chunk_id": row.id,
                    "chunk_text": row.chunk_text,
                    "metadata": row.metadata if row.metadata else {}
                }
                for row in results
            ]
            
            logger.info(f"Retrieved {len(chunks)} chunks for task {task_id}")
            return chunks
            
    except Exception as e:
        logger.error(f"ERROR retrieving chunks for task {task_id}: {e}")
        return []


def get_rag_chunks_by_job_id(job_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieve RAG chunks for a job by looking up 'retriever' agent tasks.
    
    Args:
        job_id: Orchestration Job ID
        limit: Maximum number of chunks to retrieve
    
    Returns:
        List of dicts containing:
        - chunk_id: int
        - chunk_text: str
        - metadata: dict
    """
    if document_chunks is None:
        logger.warning("document_chunks table not available")
        return []
    
    try:
        with engine.connect() as conn:
            # Import and_ for proper SQL and condition
            from sqlalchemy import and_
            
            # Strategy:
            # 1. Find tasks for this job where agent_name = 'retriever'
            # 2. Join with agent_task_sources and document_chunks
            
            stmt = select(
                document_chunks.c.id,
                document_chunks.c.chunk_text,
                document_chunks.c.metadata,
                document_chunks.c.chunk_order
            ).select_from(
                agent_tasks.join(
                    agent_task_sources,
                    agent_tasks.c.id == agent_task_sources.c.task_id
                ).join(
                    document_chunks,
                    and_(
                        agent_task_sources.c.source_id == document_chunks.c.id,
                        agent_task_sources.c.source_type == 'chunk'
                    )
                )
            ).where(
                and_(
                    agent_tasks.c.job_id == job_id,
                    agent_tasks.c.agent_name == 'retriever'  # Target the retriever agent
                )
            ).order_by(
                document_chunks.c.chunk_order
            ).limit(limit)
            
            results = conn.execute(stmt).fetchall()
            
            chunks = [
                {
                    "chunk_id": row.id,
                    "chunk_text": row.chunk_text,
                    "metadata": row.metadata if row.metadata else {}
                }
                for row in results
            ]
            
            logger.info(f"Retrieved {len(chunks)} chunks for job {job_id} (via retriever tasks)")
            return chunks
            
    except Exception as e:
        logger.error(f"ERROR retrieving chunks for job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        return []




def save_critic_evaluation_to_db(
    task_id: int,  # Use existing critic node's task_id
    job_id: int,
    evaluation_stage: int,  # 1=fact, 2=quality
    evaluation_result: Dict[str, Any],
    is_passed: bool,
    feedback: Dict[str, Any],
    metrics_detail: Dict[str, Any],
    duration_ms: int,
    evaluation_mode: str,
    iteration_number: int
) -> Optional[int]:
    """
    Save critic evaluation to TASK_EVALUATIONS table only.
    
    Does NOT create a separate agent_task. Instead, references the existing
    critic node's task_id (from @log_task decorator).
    
    Args:
        task_id: ID of the critic node's task (fact_critic or quality_critic)
        job_id: Original orchestration job ID
        evaluation_stage: 1=fact, 2=quality
        evaluation_result: Full evaluation results dict
        is_passed: Whether evaluation passed
        feedback: Structured feedback dict
        metrics_detail: Metrics dict for experiments
        duration_ms: Evaluation duration in milliseconds
        evaluation_mode: Evaluation mode (exam_quick, exam_comprehensive, etc.)
        iteration_number: Current iteration number
    
    Returns:
        task_evaluation_id if successful, None otherwise
    """
    if task_evaluations is None:
        logger.warning("task_evaluations table not available")
        return None
    
    try:
        with engine.connect() as conn:
            # Create TASK_EVALUATIONS record only
            eval_stmt = insert(task_evaluations).values(
                task_id=task_id,  # Reference existing critic node's task
                job_id=job_id,
                evaluation_stage=evaluation_stage,
                evaluation_mode=evaluation_mode,
                is_passed=is_passed,
                feedback_for_generator=feedback,
                metric_details=metrics_detail,
                evaluated_at=datetime.now(TAIPEI_TZ)
            ).returning(task_evaluations.c.id)
            
            eval_result = conn.execute(eval_stmt)
            task_evaluation_id = eval_result.scalar_one()
            
            conn.commit()
            
            logger.info(f"Saved evaluation: task_id={task_id}, eval_id={task_evaluation_id}, stage={evaluation_stage}")
            return task_evaluation_id
            
    except Exception as e:
        logger.error(f"ERROR saving evaluation for task {task_id}: {e}")
        import traceback
        traceback.print_exc()
        return None



def save_evaluation_to_db(
    job_id: int,
    parent_task_id: int,
    evaluation_result: Dict[str, Any],
    duration_ms: int,
    is_passed: bool,
    feedback: Dict[str, Any],  # Changed from str to Dict for JSONB
    metrics_detail: Dict[str, Any] = None,  # Changed from str to Dict
    evaluation_mode: str = "exam_comprehensive",  # New parameter
    iteration_number: int = 1  # Add iteration_number parameter
) -> Optional[Tuple[int, int]]:
    """
    Save evaluation results to AGENT_TASKS and TASK_EVALUATIONS tables.
    
    Creates a new AGENT_TASK for the evaluation and a TASK_EVALUATIONS record.
    
    Args:
        job_id: Original orchestration job ID
        parent_task_id: ID of the task being evaluated
        evaluation_result: Full evaluation results dict
        duration_ms: Evaluation duration in milliseconds
        is_passed: Whether evaluation passed
        feedback: Structured feedback dict for revise agent (JSONB)
        metrics_detail: Metrics dict for experiments (JSONB)
        evaluation_mode: Evaluation mode (exam_quick, exam_comprehensive, etc.)
    
    Returns:
        Tuple of (agent_task_id, task_evaluation_id) if successful, None otherwise
    """
    if task_evaluations is None:
        logger.warning("task_evaluations table not available")
        return None
    
    try:
        with engine.connect() as conn:
            # Step 1: Create AGENT_TASK for evaluation
            task_stmt = insert(agent_tasks).values(
                job_id=job_id,
                parent_task_id=parent_task_id,
                iteration_number=iteration_number,  # Use parameter instead of hardcoded 1
                agent_name='quality_critic_db',
                task_description='Save quality evaluation results to database',
                task_input={"job_id": job_id, "parent_task_id": parent_task_id},
                output=evaluation_result,
                status='completed',
                duration_ms=duration_ms,
                # model_name intentionally not set (this is a DB save operation, not LLM call)
                created_at=datetime.now(TAIPEI_TZ),
                completed_at=datetime.now(TAIPEI_TZ)
            ).returning(agent_tasks.c.id)
            
            task_result = conn.execute(task_stmt)
            evaluation_task_id = task_result.scalar_one()
            
            # Step 2: Create TASK_EVALUATIONS record
            eval_stmt = insert(task_evaluations).values(
                task_id=evaluation_task_id,
                job_id=job_id,  # New field
                evaluation_stage=2,  # 2 = Quality evaluation
                evaluation_mode=evaluation_mode,  # New field
                is_passed=is_passed,
                feedback_for_generator=feedback,  # Now JSONB dict
                metric_details=metrics_detail,  # Now JSONB dict
                evaluated_at=datetime.now(TAIPEI_TZ)
            ).returning(task_evaluations.c.id)
            
            eval_result = conn.execute(eval_stmt)
            task_evaluation_id = eval_result.scalar_one()
            
            conn.commit()
            
            logger.info(f"Saved evaluation: task_id={evaluation_task_id}, eval_id={task_evaluation_id}")
            return (evaluation_task_id, task_evaluation_id)
            
    except Exception as e:
        logger.error(f"ERROR saving evaluation for job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        return None
