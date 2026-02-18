from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from sqlalchemy import select, text, insert, update
import json
from datetime import datetime

from backend.app.agents.debugging.db import engine
from backend.app.agents.debugging.oj_models import Problem, PrecodingQuestion
from backend.app.agents.debugging.problem_generate.code_explanation import generate_explanation_questions
from backend.app.agents.debugging.problem_generate.code_debugging import generate_debugging_questions
from backend.app.agents.debugging.problem_generate.code_architecture import generate_architecture_questions

router = APIRouter(prefix="/teacher/problem", tags=["Teacher Problem Management"])

# --- Pydantic Models for Request ---

class ProblemData(BaseModel):
    problem_id: str
    title: str
    description: str
    input_description: str
    output_description: str
    samples: List[Dict[str, str]]
    hint: Optional[str] = None
    test_cases: Optional[List[Dict[str, Any]]] = None
    time_limit: Optional[int] = 1000
    memory_limit: Optional[int] = 256
    judge_type: Optional[str] = "stdio" # stdio or function
    entry_point: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    solution_code: Optional[str] = None

class GeneratedContent(BaseModel):
    content: Any # Use Any to allow structured list or dict

def nl_to_br(text: str) -> str:
    if not text: return ""
    return text.replace("\n", "<br>")

def br_to_nl(text: str) -> str:
    if not text: return ""
    return text.replace("<br>", "\n")

# --- Endpoints ---

@router.get("/list")
def get_all_problems():
    """
    Get a list of all problems (id and title) for the dropdown.
    """
    try:
        with engine.connect() as conn:
            stmt = select(Problem.problem_id, Problem.title).order_by(Problem.problem_id)
            rows = conn.execute(stmt).fetchall()
            return {
                "status": "success",
                "data": [{"problem_id": r.problem_id, "title": r.title} for r in rows]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=Dict[str, str])
def create_or_update_problem(problem: ProblemData):
    """
    Create or Update a Problem.
    Auto-converts newlines to <br> for description fields.
    """
    try:
        with engine.begin() as conn:
            # Check if exists
            stmt = select(Problem).where(Problem.problem_id == problem.problem_id)
            existing = conn.execute(stmt).fetchone()

            problem_dict = problem.dict()
            
            # Convert newlines to <br>
            for field in ["description", "input_description", "output_description", "hint"]:
                if problem_dict.get(field):
                    problem_dict[field] = nl_to_br(problem_dict[field])

            if not existing:
                 problem_dict["create_time"] = datetime.now()
            
            if existing:
                # Update
                update_stmt = update(Problem).where(Problem.problem_id == problem.problem_id).values(**problem_dict)
                conn.execute(update_stmt)
                msg = f"Problem {problem.problem_id} updated."
            else:
                # Insert
                insert_stmt = insert(Problem).values(**problem_dict)
                conn.execute(insert_stmt)
                msg = f"Problem {problem.problem_id} created."
                
        return {"status": "success", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{problem_id}")
def get_full_problem(problem_id: str):
    try:
        with engine.connect() as conn:
            stmt = select(Problem).where(Problem.problem_id == problem_id)
            row = conn.execute(stmt).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Problem not found")
            
            # Map Row to Dict
            mapping = row._mapping
            data = dict(mapping)
            
            # Convert <br> to newlines
            for field in ["description", "input_description", "output_description", "hint"]:
                if data.get(field):
                    data[field] = br_to_nl(data[field])

            # Also get generation status from PrecodingQuestion table
            pq_stmt = select(PrecodingQuestion).where(PrecodingQuestion.problem_id == problem_id)
            pq_row = conn.execute(pq_stmt).fetchone()
            
            precoding_data = {}
            if pq_row:
                pq_mapping = pq_row._mapping
                precoding_data = {
                     "explanation": pq_mapping.get("explain_code_question"),
                     "debugging": pq_mapping.get("error_code_question"),
                     "architecture": pq_mapping.get("correct_code_template"),
                     # logic_question is not in this task?
                }
            
            data["precoding"] = precoding_data
            
            return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GenerateRequest(BaseModel):
    core_concept: Optional[str] = None
    allowed_scope: Optional[List[str]] = None

@router.post("/{problem_id}/generate/{gen_type}")
def generate_content(
    problem_id: str, 
    gen_type: str = Path(..., regex="^(explanation|debugging|architecture)$"),
    request_body: GenerateRequest = None
):
    """
    Trigger generation for a specific type.
    gen_type: 'explanation', 'debugging', 'architecture'
    """
    try:
        # Default values if no body provided
        core_concept = request_body.core_concept if request_body else None
        allowed_concepts = request_body.allowed_scope if request_body else None

        # 1. Fetch Problem Data
        with engine.connect() as conn:
            stmt = select(Problem).where(Problem.problem_id == problem_id)
            row = conn.execute(stmt).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Problem not found")
            
            mapping = row._mapping
            # Prepare problem_data tuple
            # For architectureGen, last element should be solution_code
            problem_data = (
                mapping["title"],
                mapping["description"],
                mapping["input_description"],
                mapping["output_description"],
                mapping["samples"],
                mapping.get("solution_code", "") 
            )
            
        # 2. Generate
        result = None
        target_column = ""
        
        if gen_type == "explanation":
            result = generate_explanation_questions(problem_data, problem_id, manual_unit=core_concept, allowed_concepts=allowed_concepts)
            target_column = "explain_code_question"
        elif gen_type == "debugging":
            result = generate_debugging_questions(problem_data, problem_id, manual_unit=core_concept, allowed_concepts=allowed_concepts)
            target_column = "error_code_question"
        elif gen_type == "architecture":
             result = generate_architecture_questions(problem_data, problem_id, manual_unit=core_concept, allowed_concepts=allowed_concepts)
             # Note: generate_architecture_questions returns a dict string or dict?
             # My implementation returns a dict (model_dump()).
             # Wait, code_architecture.py returns `completion.choices[0].message.parsed.model_dump()`.
             target_column = "correct_code_template"
        
        if result is None:
             raise HTTPException(status_code=500, detail="Generation failed (returned None).")

        # 3. Save to PrecodingQuestion table
        # We save directly here to persist the generated result.
        # User also wants manual modify.
        # So we return the result to frontend, AND save it?
        # Or just return it? "Allowing teachers to regenerate or manually modify".
        # If we save it now, user can fetch it. If user cancels, we might want to not save?
        # But usually generation implies overwriting.
        # Let's save it.
        
        with engine.begin() as conn:
             # Check if PrecodingQuestion exists
             check_stmt = select(PrecodingQuestion).where(PrecodingQuestion.problem_id == problem_id)
             existing_pq = conn.execute(check_stmt).fetchone()
             
             if existing_pq:
                 # Update
                 # We need to construct the update dict carefully
                 update_vals = {target_column: result}
                 conn.execute(update(PrecodingQuestion).where(PrecodingQuestion.problem_id == problem_id).values(**update_vals))
             else:
                 # Insert
                 insert_vals = {"problem_id": problem_id, target_column: result}
                 conn.execute(insert(PrecodingQuestion).values(**insert_vals))
                 
        return {"status": "success", "data": result}
             
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{problem_id}/save/{gen_type}")
def save_content(problem_id: str, payload: GeneratedContent, gen_type: str = Path(..., regex="^(explanation|debugging|architecture)$")):
    """
    Save manually edited content.
    """
    try:
        target_column = ""
        if gen_type == "explanation":
            target_column = "explain_code_question"
        elif gen_type == "debugging":
            target_column = "error_code_question"
        elif gen_type == "architecture":
            target_column = "correct_code_template"

        with engine.begin() as conn:
             # Check if PrecodingQuestion exists
             check_stmt = select(PrecodingQuestion).where(PrecodingQuestion.problem_id == problem_id)
             existing_pq = conn.execute(check_stmt).fetchone()
             
             if existing_pq:
                 update_vals = {target_column: payload.content}
                 conn.execute(update(PrecodingQuestion).where(PrecodingQuestion.problem_id == problem_id).values(**update_vals))
             else:
                 insert_vals = {"problem_id": problem_id, target_column: payload.content}
                 conn.execute(insert(PrecodingQuestion).values(**insert_vals))
                 
        return {"status": "success", "message": "Content saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


