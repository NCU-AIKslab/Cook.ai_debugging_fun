"""
Utility functions for logging orchestration and agent task data to the database.
"""
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, MetaData, Table, insert, update, select, func, text, Column, Integer, String
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import json
import logging

# --- Timezone and Database Setup ---
TAIPEI_TZ = timezone(timedelta(hours=8))
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

engine = create_engine(DATABASE_URL)
metadata = MetaData()

logger = logging.getLogger(__name__)

# --- Table Reflection ---
# Reflect existing tables to avoid re-declaring them
try:
    metadata.reflect(bind=engine) # Reflect all tables
    orchestration_jobs = Table('orchestration_jobs', metadata, autoload_with=engine)
    agent_tasks = Table('agent_tasks', metadata, autoload_with=engine)
    generated_contents = Table('generated_contents', metadata, autoload_with=engine)
    agent_task_sources = Table('agent_task_sources', metadata, autoload_with=engine)
except Exception as e:
    logger.error(f"Error reflecting database tables: {e}")
    # Define tables with key columns as a fallback if reflection fails
    # These definitions are minimal and might need more columns for full functionality
    orchestration_jobs = Table('orchestration_jobs', metadata,
        Column('id', Integer, primary_key=True),
        Column('status', String),
        Column('final_output_id', Integer),
        Column('total_iterations', Integer),
        Column('total_prompt_tokens', Integer),
        Column('total_completion_tokens', Integer),
        Column('total_latency_ms', Integer),
        Column('estimated_carbon_g', Integer),
        Column('updated_at', datetime),
        # Add other essential columns if needed for the script to be parsable
    )
    agent_tasks = Table('agent_tasks', metadata,
        Column('id', Integer, primary_key=True),
        Column('job_id', Integer),
        Column('status', String),
        Column('prompt_tokens', Integer),
        Column('completion_tokens', Integer),
        Column('duration_ms', Integer),
        Column('estimated_cost_usd', Integer),
        Column('iteration_number', Integer),
        Column('output', String), # Assuming JSON string for output
        Column('error_message', String),
        Column('completed_at', datetime),
        # ...
    )
    generated_contents = Table('generated_contents', metadata,
        Column('id', Integer, primary_key=True),
        Column('content', String), # Assuming JSON string for content
        Column('title', String),
    )
    agent_task_sources = Table('agent_task_sources', metadata,
        Column('task_id', Integer, primary_key=True),
        Column('source_type', String, primary_key=True),
        Column('source_id', Integer, primary_key=True),
    )

import functools

# --- Decorator for Task Logging ---

def log_task(agent_name: str, task_description: str, input_extractor: Optional[callable] = None):
    """
    A decorator that wraps a LangGraph node function to automatically handle
    database logging for task creation, completion, and failure.
    
    Supports both sync and async functions.
    
    Args:
        agent_name (str): The name of the agent/node.
        task_description (str): A brief description of the task performed by the node.
        input_extractor (Optional[callable]): A function that takes the 'state' dictionary
                                              and returns a dictionary representing the
                                              relevant input for this task. If None,
                                              defaults to {"user_query": state.get("user_query")}.
    """
    def decorator(func):
        # Check if function is async
        import asyncio
        import inspect
        is_async = asyncio.iscoroutinefunction(func)
        
        if is_async:
            # Async wrapper
            @functools.wraps(func)
            async def async_wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
                # Determine task_input based on input_extractor or default
                extracted_task_input = None
                if input_extractor:
                    try:
                        extracted_task_input = input_extractor(state)
                    except Exception as e:
                        logger.warning(f"Failed to extract task input for '{agent_name}': {e}")
                        extracted_task_input = {"user_query": state.get("user_query")}
                else:
                    extracted_task_input = {"user_query": state.get("user_query")}

                task_id = create_task(
                    job_id=state['job_id'],
                    agent_name=agent_name,
                    task_description=task_description,
                    task_input=extracted_task_input,
                    parent_task_id=state.get("parent_task_id"),
                    iteration_number=state.get("iteration_count", 1)
                )
                
                if task_id is None:
                    error_message = f"Failed to create database task for agent '{agent_name}'."
                    logger.error(error_message)
                    return {"error": error_message}

                start_time = time.perf_counter()
                
                # Record initial iteration_count for later comparison
                initial_iteration = state.get("iteration_count", 1)
                
                try:
                    state_for_node = state.copy()
                    state_for_node['current_task_id'] = task_id
                    
                    # Execute the async node function
                    result = await func(state_for_node)
                    
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    
                    # Check if iteration_count changed during node execution
                    # This happens when a skill node increments it for refinement iterations
                    new_iteration = result.get("iteration_count", initial_iteration)                    
                    if new_iteration != initial_iteration:
                        # Update the task's iteration_number in database
                        try:
                            with engine.connect() as conn:
                                stmt = update(agent_tasks).where(
                                    agent_tasks.c.id == task_id
                                ).values(iteration_number=new_iteration)
                                conn.execute(stmt)
                                conn.commit()
                                logger.info(f"✅ Updated task {task_id} iteration_number from {initial_iteration} to {new_iteration}")
                        except Exception as e:
                            logger.warning(f"Failed to update iteration_number for task {task_id}: {e}")
                    
                    # Pop router_output first if it exists (for router nodes)
                    router_output = result.pop("_router_output", None)
                    
                    prompt_tokens = result.pop("prompt_tokens", None)
                    completion_tokens = result.pop("completion_tokens", None)
                    estimated_cost_usd = result.pop("estimated_cost_usd", None)
                    model_name = result.pop("model_name", None)

                    if result.get("error"):
                        update_task(
                            task_id, 'failed', 
                            error_message=result["error"], 
                            duration_ms=duration_ms
                        )
                    else:
                        # Use minimal output for routers
                        db_output = router_output or result
                        update_task(
                            task_id, 'completed', 
                            output=db_output, 
                            duration_ms=duration_ms,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            estimated_cost_usd=estimated_cost_usd,
                            model_name=model_name
                        )
                    
                    final_result = state.copy()

                    final_result.update(result)

                    if "error" not in final_result:
                        final_result["parent_task_id"] = task_id
                        final_result["current_task_id"] = task_id
                        
                    return final_result

                except Exception as e:
                    error_message = str(e)
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    update_task(task_id, 'failed', error_message=error_message, duration_ms=duration_ms)
                    return {"error": error_message}
            
            return async_wrapper
        
        else:
            # Sync wrapper (original implementation)
            @functools.wraps(func)
            def sync_wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
                extracted_task_input = None
                if input_extractor:
                    try:
                        extracted_task_input = input_extractor(state)
                    except Exception as e:
                        logger.warning(f"Failed to extract task input for '{agent_name}': {e}")
                        extracted_task_input = {"user_query": state.get("user_query")}
                else:
                    extracted_task_input = {"user_query": state.get("user_query")}

                task_id = create_task(
                    job_id=state['job_id'],
                    agent_name=agent_name,
                    task_description=task_description,
                    task_input=extracted_task_input,
                    parent_task_id=state.get("parent_task_id"),
                    iteration_number=state.get("iteration_count", 1)
                )
                
                if task_id is None:
                    error_message = f"Failed to create database task for agent '{agent_name}'."
                    logger.error(error_message)
                    return {"error": error_message}

                start_time = time.perf_counter()
                
                # Record initial iteration_count for later comparison
                initial_iteration = state.get("iteration_count", 1)
                
                try:
                    state_for_node = state.copy()
                    state_for_node['current_task_id'] = task_id
                    
                    result = func(state_for_node)
                    
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    
                    # Check if iteration_count changed during node execution (same as async)
                    new_iteration = result.get("iteration_count", initial_iteration)
                    if new_iteration != initial_iteration:
                        # Update the task's iteration_number in database
                        try:
                            with engine.connect() as conn:
                                stmt = update(agent_tasks).where(
                                    agent_tasks.c.id == task_id
                                ).values(iteration_number=new_iteration)
                                conn.execute(stmt)
                                conn.commit()
                                logger.info(f"✅ Updated task {task_id} iteration_number from {initial_iteration} to {new_iteration}")
                        except Exception as e:
                            logger.warning(f"Failed to update iteration_number for task {task_id}: {e}")
                    
                    # Pop router_output first if it exists (for router nodes)
                    router_output = result.pop("_router_output", None)
                    
                    prompt_tokens = result.pop("prompt_tokens", None)
                    completion_tokens = result.pop("completion_tokens", None)
                    estimated_cost_usd = result.pop("estimated_cost_usd", None)
                    model_name = result.pop("model_name", None)

                    if result.get("error"):
                        update_task(
                            task_id, 'failed', 
                            error_message=result["error"], 
                            duration_ms=duration_ms
                        )
                    else:
                        # Use minimal output for orchestrators
                        db_output = router_output or result
                        update_task(
                            task_id, 'completed', 
                            output=db_output, 
                            duration_ms=duration_ms,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            estimated_cost_usd=estimated_cost_usd,
                            model_name=model_name
                        )
                    
                    final_result = state.copy()

                    final_result.update(result)

                    if "error" not in final_result:
                        final_result["parent_task_id"] = task_id
                        final_result["current_task_id"] = task_id
                        
                    return final_result

                except Exception as e:
                    error_message = str(e)
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    update_task(task_id, 'failed', error_message=error_message, duration_ms=duration_ms)
                    return {"error": error_message}
            
            return sync_wrapper
    
    return decorator

# --- Job-level Logging ---

def create_job(user_id: int, input_prompt: str, workflow_type: str, experiment_config: Optional[Dict] = None) -> Optional[int]:
    """Creates a new record in the orchestration_jobs table."""
    try:
        with engine.connect() as conn:
            stmt = insert(orchestration_jobs).values(
                user_id=user_id,
                input_prompt=input_prompt,
                status='planning',
                workflow_type=workflow_type,
                experiment_config=experiment_config,
                created_at=datetime.now(TAIPEI_TZ),
                updated_at=datetime.now(TAIPEI_TZ)
            ).returning(orchestration_jobs.c.id)
            result = conn.execute(stmt)
            job_id = result.scalar_one()
            conn.commit()
            logger.info(f"Created job {job_id} for workflow '{workflow_type}'.")
            return job_id
    except Exception as e:
        logger.error(f"Failed to create job. Reason: {e}")
        return None

def update_job_status(job_id: int, status: str, error_message: Optional[str] = None):
    """Updates the status and error message of a job."""
    try:
        with engine.connect() as conn:
            stmt = update(orchestration_jobs).where(orchestration_jobs.c.id == job_id).values(
                status=status,
                error_message=error_message,
                updated_at=datetime.now(TAIPEI_TZ)
            )
            conn.execute(stmt)
            conn.commit()
            logger.info(f"Updated job {job_id} status to '{status}'.")
    except Exception as e:
        logger.error(f"Failed to update job {job_id}. Reason: {e}")

def update_job_final_output(job_id: int, final_output_id: int):
    """Updates the final_output_id of a job."""
    try:
        with engine.connect() as conn:
            stmt = update(orchestration_jobs).where(orchestration_jobs.c.id == job_id).values(
                final_output_id=final_output_id,
                updated_at=datetime.now(TAIPEI_TZ)
            )
            conn.execute(stmt)
            conn.commit()
            logger.info(f"Updated job {job_id} with final_output_id: {final_output_id}.")
    except Exception as e:
        logger.error(f"Failed to update job {job_id} final_output_id. Reason: {e}")

def get_job_status(job_id: int) -> Optional[str]:
    """Retrieves the current status of a job."""
    try:
        with engine.connect() as conn:
            stmt = select(orchestration_jobs.c.status).where(orchestration_jobs.c.id == job_id)
            status = conn.execute(stmt).scalar_one_or_none()
            return status
    except Exception as e:
        logger.error(f"Failed to get status for job {job_id}. Reason: {e}")
        return None

# --- Task-level Logging ---

def create_task(
    job_id: int, 
    agent_name: str, 
    task_description: str, 
    task_input: Optional[Dict] = None, 
    model_name: Optional[str] = None, 
    parent_task_id: Optional[int] = None, 
    model_parameters: Optional[Dict] = None,
    iteration_number: int = 1
) -> Optional[int]:
    """Creates a new record in the agent_tasks table and returns its ID and start time."""
    try:
        with engine.connect() as conn:
            stmt = insert(agent_tasks).values(
                job_id=job_id,
                agent_name=agent_name,
                task_description=task_description,
                task_input=task_input,
                status='in_progress',
                model_name=model_name,
                parent_task_id=parent_task_id,
                model_parameters=model_parameters,
                iteration_number=iteration_number,
                created_at=datetime.now(TAIPEI_TZ)
            ).returning(agent_tasks.c.id)
            result = conn.execute(stmt)
            task_id = result.scalar_one()
            conn.commit()
            logger.info(f"Created task {task_id} for agent '{agent_name}' (iteration {iteration_number}, parent={parent_task_id}).")
            return task_id
    except Exception as e:
        logger.error(f"Failed to create task for agent '{agent_name}'. Reason: {e}")
        return None

def update_task(
    task_id: int,
    status: str,
    output: Optional[Any] = None, # Changed type hint to Any
    error_message: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    duration_ms: Optional[int] = None,
    estimated_cost_usd: Optional[float] = None,
    model_name: Optional[str] = None  # Add model_name parameter
):
    """Updates an agent_task record upon completion or failure."""
    try:
        with engine.connect() as conn:
            processed_output = None
            if output is not None:
                if isinstance(output, (dict, list)):
                    processed_output = output
                elif isinstance(output, str):
                    try:
                        processed_output = json.loads(output)
                    except json.JSONDecodeError:
                        processed_output = {"text_output": output} # Wrap plain strings
                else:
                    processed_output = {"value": str(output)} # Catch all other types

            values = { # Renamed from values_to_update to values as per snippet
                "status": status,
                "output": processed_output, # Use the processed output
                "error_message": error_message,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "duration_ms": duration_ms,
                "completed_at": datetime.now(TAIPEI_TZ),
                "estimated_cost_usd": estimated_cost_usd,
                "model_name": model_name  # Add model_name to values
            }
            # Filter out None values so they don't overwrite existing data in the DB
            values = {k: v for k, v in values.items() if v is not None}
            


            stmt = update(agent_tasks).where(agent_tasks.c.id == task_id).values(**values)
            conn.execute(stmt)
            conn.commit()
            logger.info(f"Updated task {task_id} to status '{status}'.")
    except Exception as e:
        logger.error(f"Failed to update task {task_id}. Reason: {e}")


# --- Content and Source Logging ---

def log_task_sources(task_id: int, source_chunks: Optional[List[Dict]] = None):
    """Logs the retrieved source chunks for a specific task."""
    if not source_chunks:
        return

    try:
        with engine.connect() as conn:
            records_to_insert = [
                {
                    "task_id": task_id,
                    "source_type": 'chunk',
                    "source_id": chunk.get("chunk_id")
                }
                for chunk in source_chunks if chunk.get("chunk_id") is not None
            ]
            
            if not records_to_insert:
                return

            # Use a transaction for the insert
            with conn.begin():
                conn.execute(insert(agent_task_sources), records_to_insert)
            
            logger.info(f"Logged {len(records_to_insert)} sources for task {task_id}.")

    except Exception as e:
        logger.error(f"Failed to log sources for task {task_id}. Reason: {e}")


def save_generated_content(task_id: int, content_type: str, title: str, content: str) -> Optional[int]:
    """Saves generated content to the GENERATED_CONTENTS table."""
    try:
        with engine.connect() as conn:
            # The 'content' column in the DB is JSON. Parse the incoming JSON string.
            parsed_content = json.loads(content)
            
            # Inject the content_type as a 'type' field into the parsed content
            if isinstance(parsed_content, dict):
                parsed_content["type"] = content_type
            elif isinstance(parsed_content, list):
                # If it's a list, we might need to decide how to handle it.
                # For now, we'll wrap it in a dict with the type.
                parsed_content = {"type": content_type, "data": parsed_content}
            else:
                # For other types (e.g., string, int), wrap it in a dict with the type.
                parsed_content = {"type": content_type, "value": parsed_content}
            
            stmt = insert(generated_contents).values(
                source_agent_task_id=task_id,
                content_type=content_type,
                title=title,
                content=parsed_content, # Store the parsed JSON object directly
                created_at=datetime.now(TAIPEI_TZ),
                updated_at=datetime.now(TAIPEI_TZ)
            ).returning(generated_contents.c.id)
            
            result = conn.execute(stmt)
            content_id = result.scalar_one()
            conn.commit()
            
            logger.info(f"Saved generated content for task {task_id}. New content ID: {content_id}.")
            return content_id
            
    except Exception as e:
        logger.error(f"Failed to save generated content for task {task_id}. Reason: {e}")
        return None

def get_generated_content_by_id(content_id: int) -> Optional[Dict]:
    """Retrieves generated content by its ID from the GENERATED_CONTENTS table."""
    try:
        with engine.connect() as conn:
            stmt = select(generated_contents.c.content, generated_contents.c.title).where(generated_contents.c.id == content_id)
            result = conn.execute(stmt).fetchone()
            if result:
                return {"title": result.title, "data": result.content}
            return None
    except Exception as e:
        logger.error(f"Failed to retrieve generated content {content_id}. Reason: {e}")
        return None

def get_job_final_output_id(job_id: int) -> Optional[int]:
    """Retrieves the final_output_id for a given job_id from the orchestration_jobs table."""
    try:
        with engine.connect() as conn:
            stmt = select(orchestration_jobs.c.final_output_id).where(orchestration_jobs.c.id == job_id)
            result = conn.execute(stmt).scalar_one_or_none()
            return result
    except Exception as e:
        logger.error(f"Failed to retrieve final_output_id for job {job_id}. Reason: {e}")
        return None

def get_job_cumulative_metrics(job_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves cumulative metrics from all agent_tasks for a given job.
    
    Returns a dictionary with:
    - total_iterations: Count of distinct iteration_number values
    - total_prompt_tokens: Sum of all prompt_tokens
    - total_completion_tokens: Sum of all completion_tokens
    - total_latency_ms: Sum of all duration_ms
    - estimated_carbon_g: Estimated carbon emissions (placeholder)
    """
    try:
        with engine.connect() as conn:
            # Query to aggregate metrics
            stmt = select(
                func.count(func.distinct(agent_tasks.c.iteration_number)).label('total_iterations'),
                func.coalesce(func.sum(agent_tasks.c.prompt_tokens), 0).label('total_prompt_tokens'),
                func.coalesce(func.sum(agent_tasks.c.completion_tokens), 0).label('total_completion_tokens'),
                func.coalesce(func.sum(agent_tasks.c.duration_ms), 0).label('total_latency_ms')
            ).where(agent_tasks.c.job_id == job_id)
            
            result = conn.execute(stmt).fetchone()
            
            if result:
                return {
                    "total_iterations": result.total_iterations or 0,
                    "total_prompt_tokens": int(result.total_prompt_tokens),
                    "total_completion_tokens": int(result.total_completion_tokens),
                    "total_latency_ms": int(result.total_latency_ms),
                    "estimated_carbon_g": 0  # Placeholder for future carbon calculation
                }
            return None
    except Exception as e:
        logger.error(f"Failed to get cumulative metrics for job {job_id}. Reason: {e}")
        return None

def update_job_iterations_and_cost(job_id: int):
    """
    Updates the orchestration_jobs table with cumulative metrics from all related agent_tasks.
    This should be called when a job completes.
    """
    try:
        metrics = get_job_cumulative_metrics(job_id)
        if not metrics:
            logger.warning(f"No metrics found for job {job_id}.")
            return
        
        with engine.connect() as conn:
            stmt = update(orchestration_jobs).where(orchestration_jobs.c.id == job_id).values(
                total_iterations=metrics["total_iterations"],
                total_prompt_tokens=metrics["total_prompt_tokens"],
                total_completion_tokens=metrics["total_completion_tokens"],
                total_latency_ms=metrics["total_latency_ms"],
                estimated_carbon_g=metrics["estimated_carbon_g"],
                updated_at=datetime.now(TAIPEI_TZ)
            )
            conn.execute(stmt)
            conn.commit()
            logger.info(f"Updated job {job_id} with cumulative metrics: {metrics['total_iterations']} iterations.")
    except Exception as e:
        logger.error(f"Failed to update job {job_id} iterations and cost. Reason: {e}")

