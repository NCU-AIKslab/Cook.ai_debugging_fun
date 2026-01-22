import os
import json
import time
from datetime import datetime # Add this import
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .state import ExamGenerationState
from backend.app.agents.rag_agent import rag_agent
from backend.app.utils import db_logger # Add this import
from backend.app.utils.db_logger import log_task, log_task_sources

# --- Pydantic Models for Tool-based Planning ---
class Task(BaseModel):
    """A single task for generating questions."""
    type: str = Field(..., description="The type of task, e.g., 'multiple_choice', 'short_answer', 'true_false'.")
    count: int = Field(..., description="The number of questions to generate for this task.")
    topic: Optional[str] = Field(None, description="The specific topic for this task, if any.")

class Plan(BaseModel):
    """A structured plan consisting of a list of generation tasks."""
    main_title: str = Field(..., description="A concise, professional title (in Traditional Chinese) that clearly describes the topic and focus of the generated exam questions based on the user's query.")
    tasks: List[Task] = Field(..., description="A list of generation tasks to perform based on the user's query.")

# --- Pydantic Models for Question Types ---
class Source(BaseModel):
    page_number: str = Field(..., description="The page number from which the information was sourced.")
    evidence: str = Field(..., description="A brief quote or explanation from the text that supports the answer.")

class MultipleChoiceQuestion(BaseModel):
    question_number: int = Field(..., description="The sequential number of the question.")
    question_text: str = Field(..., description="The text of the multiple-choice question.")
    options: Dict[str, str] = Field(..., description="A dictionary of options, e.g., {'A': 'Option Text A', ...}.")
    correct_answer: str = Field(..., description="The letter corresponding to the correct answer (e.g., 'A', 'B').")
    source: Source = Field(..., description="The source of the answer within the provided document.")

class TrueFalseQuestion(BaseModel):
    question_number: int = Field(..., description="The sequential number of the question.")
    statement_text: str = Field(..., description="The statement to be evaluated as true or false.")
    correct_answer: str = Field(..., description="The correct answer, either 'True' or 'False'.")
    source: Source = Field(..., description="The source of the answer within the provided document.")

class ShortAnswerQuestion(BaseModel):
    question_number: int = Field(..., description="The sequential number of the question.")
    question_text: str = Field(..., description="The text of the short-answer question.")
    sample_answer: str = Field(..., description="A detailed sample correct answer for the question.")
    source: Source = Field(..., description="The source of the answer within the provided document.")

# A model to hold a list of questions for a specific type, for tool calling
class MultipleChoiceQuestionsList(BaseModel):
    questions: List[MultipleChoiceQuestion] = Field(..., description="A list of multiple-choice questions.")

class TrueFalseQuestionsList(BaseModel):
    questions: List[TrueFalseQuestion] = Field(..., description="A list of true/false questions.")

class ShortAnswerQuestionsList(BaseModel):
    questions: List[ShortAnswerQuestion] = Field(..., description="A list of short-answer questions.")


# --- Pricing Info ---
# Prices per 1 million tokens in USD
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
}


# --- Helper Functions ---

def get_llm() -> ChatOpenAI:
    """Initializes the ChatOpenAI model."""
    model_name = os.getenv("GENERATOR_MODEL", "gpt-4o-mini")
    # Note: To see verbose output from LangChain, you can add `verbose=True`
    return ChatOpenAI(model=model_name)

def call_openai_api(llm: ChatOpenAI, prompt: str, images: List[str] = None) -> Any:
    """Calls the LLM with a multimodal payload and returns the full response object."""
    message_content = [{"type": "text", "text": prompt}]
    if images:
        for image_uri in images:
            message_content.append({
                "type": "image_url",
                "image_url": {"url": image_uri, "detail": "low"}
            })
    
    messages = [
        SystemMessage(content="You are a helpful assistant expert in creating educational materials."),
        HumanMessage(content=message_content)
    ]
    response = llm.invoke(messages)
    return response

def _prepare_multimodal_content(retrieved_page_content: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    """Prepares content from structured page content for the LLM."""
    max_images = int(os.getenv("MAX_IMAGES_PER_PROMPT", "5"))
    combined_text_parts, image_data_urls, image_source_map = [], [], []

    if not retrieved_page_content:
        return "", []

    for item in retrieved_page_content:
        if item.get("type") == "structured_page_content":
            page_num = item.get("page_number", "Unknown")
            combined_text_parts.append(f"\n\n--- [START] Source: Page {page_num} ---")
            page_content = item.get("content", [])
            for element in page_content:
                if element.get("type") == "text":
                    combined_text_parts.append(element.get("content", ""))
                elif element.get("type") == "image" and len(image_data_urls) < max_images:
                    base64_data = element.get("base64")
                    if base64_data:
                        mime_type = element.get("mime_type", "image/jpeg")
                        valid_image_url = f"data:{mime_type};base64,{base64_data}" if not base64_data.startswith("data:") else base64_data
                        image_data_urls.append(valid_image_url)
                        image_index = len(image_data_urls)
                        combined_text_parts.append(f"\n[Image {image_index} is here. Source: Page {page_num}]\n")
                        image_source_map.append(f"Image {image_index}: Sourced from Page {page_num}")
            combined_text_parts.append(f"--- [END] Source: Page {page_num} ---\n")

    final_text = "\n".join(combined_text_parts)
    if image_source_map:
        final_text += "\n\n--- Image Source Key ---\n" + "\n".join(image_source_map)
    return final_text, image_data_urls

# --- Node Functions ---

@log_task(agent_name="retriever", task_description="Retrieve relevant document chunks using RAG.", input_extractor=lambda state: {"query": state.get("query"), "unique_content_id": state.get("unique_content_id")})
def retrieve_chunks_node(state: ExamGenerationState) -> dict:
    """Retrieves context using RAGAgent and populates the state."""
    try:
        rag_results = rag_agent.search(user_prompt=state["query"], unique_content_id=state["unique_content_id"])
        # The decorator has already created the task and injected its ID into the state
        log_task_sources(state["current_task_id"], rag_results["text_chunks"])

        return {
            "retrieved_text_chunks": rag_results["text_chunks"],
            "retrieved_page_content": rag_results["page_content"],
            "generation_plan": [],
            "final_generated_content": [],
            "generation_errors": [],
            "parent_task_id": state["current_task_id"] # Set self as parent for the next node
        }
    except Exception as e:
        return {"error": f"Failed to retrieve context: {str(e)}"}

@log_task(agent_name="plan_generation_tasks", task_description="Analyze user query to create a generation plan.", input_extractor=lambda state: {"query": state.get("query")})
def plan_generation_tasks_node(state: ExamGenerationState) -> dict:
    """Analyzes the user query to create a structured generation plan using an LLM."""
    # --- Refinement Logic ---
    critic_feedback = state.get("critic_feedback", [])
    if critic_feedback:
        latest_feedback = critic_feedback[-1]
        if latest_feedback.get("overall_status") == "fail":
            # Generate a Refinement Plan
            # We need to identify which tasks need to be re-done or refined.
            # For simplicity, we will re-generate the questions that failed.
            
            feedback_items = latest_feedback.get("feedback_items", []) # Should be "final_feedback" from CriticState
            # Note: In TeacherAgentState, we store the list of feedback dicts.
            # The structure depends on how we map CriticState to TeacherAgentState.
            # Let's assume we store the whole CriticState output or similar.
            
            # Actually, let's look at how we will pass data.
            # We need to parse the feedback to create tasks.
            
            refinement_tasks = []
            for item in feedback_items:
                # item: { "question_index": int, "type": "fact"|"quality", "feedback": [...] }
                # We need to map index back to the specific question type/task.
                # This is tricky if we don't track lineage.
                # For now, let's create a generic "refine_content" task or re-generate all?
                
                # Simpler approach for V1:
                # If feedback exists, we create a "refine_exam" task that takes the *entire* previous content + feedback
                # and asks the LLM to fix it.
                pass
            
            # Let's use a specific Refinement Task
            # Note: The Task BaseModel does not support 'id', 'description', 'dependencies', 'status', 'params'.
            # For now, we'll create a dictionary that represents this conceptual task.
            # This will require a new node to handle 'refine_exam' type tasks.
            refinement_plan_task = {
                "type": "refine_exam",
                "count": 1, # This task represents a single refinement operation
                "topic": "Refine exam questions based on critic feedback",
                "params": {
                    "feedback": latest_feedback,
                    "previous_content": state.get("final_generated_content", [])
                } # Pass the full feedback and content for the refinement agent
            }
            
            return {
                "generation_plan": [refinement_plan_task],
                "current_task": None,
                "final_generated_content": [] # Clear previous content to allow overwrite/append
            }

    # If plan exists and no feedback (or feedback passed), skip
    if state.get("generation_plan") and not critic_feedback:
        return {}
    
    if state.get("final_generated_content") and not critic_feedback:
        return {}

    try:
        llm = get_llm()
        prompt = f"Analyze the user's query to create a structured generation plan and a descriptive main title. The title should summarize the entire task in Traditional Chinese.\n\n**User Query:** \"{state['query']}\"\n\nYou must respond by calling the `Plan` tool."
        planner_llm = llm.bind_tools(tools=[Plan], tool_choice="Plan")
        messages = [SystemMessage(content="You are a helpful assistant that creates a structured generation plan and a descriptive title."), HumanMessage(content=prompt)]
        
        response = planner_llm.invoke(messages)
        
        if not response.tool_calls:
            raise ValueError("The model did not call the required 'Plan' tool.")
            
        plan = Plan(**response.tool_calls[0]['args'])

        main_title = plan.main_title
        generation_plan = [task.model_dump() for task in plan.tasks]
        
        # --- Extract tokens and cost for the decorator ---
        token_usage = response.response_metadata.get("token_usage", {})
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        model_name = llm.model_name
        pricing = MODEL_PRICING.get(model_name, {"input": 0, "output": 0})
        estimated_cost = ((prompt_tokens / 1_000_000) * pricing["input"]) + ((completion_tokens / 1_000_000) * pricing["output"])

        return {
            "generation_plan": generation_plan,
            "main_title": main_title,
            "parent_task_id": state["current_task_id"], # Pass self as parent for next nodes
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": estimated_cost,
            "model_name": model_name  # Add model_name
        }
    except Exception as e:
        error_message = f"Failed to create a generation plan: {e}"
        return {"error": error_message, "generation_errors": [{"task": "plan_generation_tasks", "error_message": str(e)}]}

def prepare_next_task_node(state: ExamGenerationState) -> ExamGenerationState:
    """Pops the next task from the plan and sets it as the current task."""
    state["error"] = None # Clear temporary error for next task
    if state.get("generation_plan") and len(state["generation_plan"]) > 0:
        state["current_task"] = state["generation_plan"].pop(0)
    else:
        state["current_task"] = None
    return state

def should_continue_router(state: ExamGenerationState) -> str:
    """Router that checks the current task and decides where to go next."""
    # If there's a temporary error from the previous task, it's already logged in generation_errors.
    # We want to continue processing other tasks if possible, or go to aggregation.
    current_task = state.get("current_task")
    if current_task:
        task_type = current_task.get("type")
        if task_type == "refine_exam":
            return "refine_exam"
        return f"generate_{task_type}" if task_type in ["multiple_choice", "short_answer", "true_false"] else "end" # Return "end" for aggregation
    return "end" # Go to aggregation if no more tasks

# --- Refactored Generation Logic ---

def _generic_generate_question(state: ExamGenerationState, task_type_name: str) -> dict:
    """
    A generic internal function that handles question generation.
    It is called by the public-facing, decorated node functions.
    It returns a dictionary with results and metrics for the decorator to log.
    """
    current_task = state.get("current_task", {})
    
    try:
        llm = get_llm()
        task_details = f"Task: Generate {current_task.get('count', 1)} {task_type_name.replace('_', ' ')} question(s)"
        if current_task.get('topic'):
            task_details += f" about '{current_task.get('topic')}'"

        combined_retrieved_text, image_data_urls = _prepare_multimodal_content(state["retrieved_page_content"])
        
        system_message_content = "You are a professional university professor (您是一位專業的大學教師) designing an exam. Your task is to generate high-quality questions based on the provided text content and images. You MUST use the provided tool to output the questions."
        
        human_message_content = [
            {"type": "text", "text": f"**--- CRITICAL PRINCIPLES ---**\n"},
            {"type": "text", "text": f"1.  **Must Provide Correct Answer:** Every question must have a clearly indicated correct answer.\n"},
            {"type": "text", "text": f"2.  **Must Cite Source with Evidence:** You MUST include the **Page Number** AND a **brief quote or explanation** from the text that supports why the answer is correct.\n"},
            {"type": "text", "text": f"3.  **Clean and Contextualize the Evidence:** The quoted text must be cleaned. Remove any formatting artifacts (like '○', bullet points, etc.). Ensure it forms a complete, coherent sentence or phrase that provides sufficient context for the answer, even if the question implies part of the context.\n"},
            {"type": "text", "text": f"4.  **Language:** All output must be in Traditional Chinese (繁體中文).\n"},
            {"type": "text", "text": f"5.  **Subject Relevance:** All questions must be strictly relevant to the main subject of the document.\n"},
            {"type": "text", "text": f"\n**--- INPUTS ---**\n"},
            {"type": "text", "text": f"- **Overall User Query:** {state['query']}\n"},
            {"type": "text", "text": f"- **Current Task:** {task_details}\n"},
            {"type": "text", "text": f"- **Retrieved Content:**\n{combined_retrieved_text}\n"},
            {"type": "text", "text": f"- **Images:** [Images are provided if available]\n"}
        ]

        if task_type_name == "multiple_choice":
            human_message_content.append({"type": "text", "text": f"\n**--- MULTIPLE CHOICE SPECIFIC INSTRUCTIONS ---**\n"})
            human_message_content.append({"type": "text", "text": f"For multiple-choice questions, you MUST provide exactly four options (A, B, C, D) for each question. This is CRITICAL. The 'options' field in the tool MUST be a dictionary with keys 'A', 'B', 'C', 'D' and their corresponding text values. DO NOT OMIT THE 'OPTIONS' FIELD. Each question requires the 'options' dictionary with four choices.\n"})
            human_message_content.append({"type": "text", "text": f"\n**--- EXAMPLE MULTIPLE CHOICE QUESTION JSON ---**\n"})
            human_message_content.append({"type": "text", "text": f"```json\n{{\n  \"questions\": [\n    {{\n      \"question_number\": 1,\n      \"question_text\": \"以下哪項是地球上最豐富的氣體？\",\n      \"options\": {{\n        \"A\": \"氧氣\",\n        \"B\": \"氮氣\",\n        \"C\": \"二氧化碳\",\n        \"D\": \"氫氣\"\n      }},\n      \"correct_answer\": \"B\",\n      \"source\": {{\n        \"page_number\": \"10\",\n        \"evidence\": \"地球大氣層約有78%是氮氣。\"\n      }}\n    }}\n  ]\n}}\n```\n"})

        if image_data_urls:
            for image_uri in image_data_urls:
                human_message_content.append({
                    "type": "image_url",
                    "image_url": {"url": image_uri, "detail": "low"}
                })

        messages = [
            SystemMessage(content=system_message_content),
            HumanMessage(content=human_message_content)
        ]

        tool_model_map = {
            "multiple_choice": MultipleChoiceQuestionsList,
            "true_false": TrueFalseQuestionsList,
            "short_answer": ShortAnswerQuestionsList,
        }
        tool_model = tool_model_map.get(task_type_name)
        if not tool_model:
            raise ValueError(f"Unsupported task type: {task_type_name}")

        tool_llm = llm.bind_tools(tools=[tool_model], tool_choice={"type": "function", "function": {"name": tool_model.__name__}})
        response = tool_llm.invoke(messages)
        
        if not response.tool_calls:
            raise ValueError("The model did not call the required tool to generate questions.")
            
        generated_questions_list = tool_model(**response.tool_calls[0]['args'])
        
        final_generated_content = {
            "type": task_type_name,
            "questions": [q.model_dump() for q in generated_questions_list.questions]
        }
        
        token_usage = response.response_metadata.get("token_usage", {})
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        model_name = llm.model_name
        pricing = MODEL_PRICING.get(model_name, {"input": 0, "output": 0})
        estimated_cost = ((prompt_tokens / 1_000_000) * pricing["input"]) + ((completion_tokens / 1_000_000) * pricing["output"])

        # The decorator will handle logging the output.
        # We append to a new list to avoid modifying state directly in a deep way.
        new_final_generated_content = state.get("final_generated_content", []) + [final_generated_content]

        return {
            "final_generated_content": new_final_generated_content,
            "main_title": state.get("main_title"), # Preserve the title
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": estimated_cost,
            "model_name": model_name  # Add model_name
        }
    except Exception as e:
        error_message = f"Error in {task_type_name} generation: {str(e)}"
        new_generation_errors = state.get("generation_errors", []) + [{"task_type": task_type_name, "error_message": str(e), "task_input": current_task}]
        return {"error": error_message, "generation_errors": new_generation_errors}

@log_task(agent_name="generate_multiple_choice", task_description="Generate multiple choice questions.", input_extractor=lambda state: {"current_task": state.get("current_task")})
def generate_multiple_choice_node(state: ExamGenerationState) -> dict:
    return _generic_generate_question(state, "multiple_choice")

@log_task(agent_name="generate_short_answer", task_description="Generate short answer questions.", input_extractor=lambda state: {"current_task": state.get("current_task")})
def generate_short_answer_node(state: ExamGenerationState) -> dict:
    return _generic_generate_question(state, "short_answer")

@log_task(agent_name="generate_true_false", task_description="Generate true/false questions.", input_extractor=lambda state: {"current_task": state.get("current_task")})
def generate_true_false_node(state: ExamGenerationState) -> dict:
    return _generic_generate_question(state, "true_false")

@log_task(agent_name="refine_exam", task_description="Refining exam questions based on feedback.", input_extractor=lambda state: {"feedback_count": len(state.get("critic_feedback", []))})
def refine_exam_node(state: ExamGenerationState) -> dict:
    """
    Refines the generated exam questions based on critic feedback.
    """
    critic_feedback = state.get("critic_feedback", [])
    if not critic_feedback:
        return {"error": "No feedback found for refinement."}
        
    latest_feedback = critic_feedback[-1]
    
    # We need to access the previous content.
    # In plan_generation_tasks_node, we cleared final_generated_content.
    # BUT we need it for refinement.
    # We should have preserved it or passed it in params.
    # The task params has 'feedback'.
    # Let's assume the state still has 'final_generated_content' because we are in a loop?
    # No, plan_generation_tasks_node returned "final_generated_content": [] to clear it.
    # This is a problem.
    # The planner should NOT clear it if it's a refinement task, OR it should pass it in params.
    # Let's assume for now we didn't clear it (I need to check plan_generation_tasks_node again).
    # In Step 262, I added "final_generated_content": [] to the return dict.
    # So it IS cleared.
    
    # I must fix plan_generation_tasks_node to NOT clear it if refining, 
    # OR pass it to the task.
    # Passing to task is safer.
    
    # But wait, I can't easily change plan_generation_tasks_node in this same tool call if I don't target it.
    # Let's assume I will fix plan_generation_tasks_node in the next step or use a workaround.
    # Workaround: The state passed to this node is the accumulated state.
    # If planner returned [], then state['final_generated_content'] is [].
    # So I MUST fix planner.
    
    # For now, let's implement the node assuming content is available in state or params.
    # I'll check state.get("final_generated_content") or params.
    
    current_task = state.get("current_task", {})
    params = current_task.get("params", {})
    
    # If content is empty, we are stuck.
    # Let's try to recover from history?
    # TeacherAgentState has 'final_generated_content'.
    # But we are in ExamGenerationState.
    # The TeacherAgent passes 'final_generated_content' down? No.
    
    # I will modify plan_generation_tasks_node to pass 'previous_content' in params.
    
    current_content = params.get("previous_content", state.get("final_generated_content", []))
    
    # Construct Prompt
    feedback_str = json.dumps(latest_feedback, ensure_ascii=False, indent=2)
    content_str = json.dumps(current_content, ensure_ascii=False, indent=2)
    
    system_prompt = (
        "You are an expert educational content editor. "
        "Your task is to refine exam questions based on specific feedback from a critic. "
        "Ensure all output is in Traditional Chinese (繁體中文)."
    )
    
    user_prompt = (
        f"Here are the original questions:\n{content_str}\n\n"
        f"Here is the feedback from the critic:\n{feedback_str}\n\n"
        "Please rewrite the questions to address *all* the feedback points. "
        "Return the FULL set of questions (including those that didn't need changes) in the same JSON format."
    )
    
    llm = get_llm()
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    
    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        refined_content = json.loads(content)
        
        # Ensure it's a list
        if isinstance(refined_content, dict):
             refined_content = [refined_content]
             
        return {
            "final_generated_content": refined_content,
            "current_task": None # Task done
        }
    except Exception as e:
        return {"error": f"Refinement failed: {str(e)}"}

def handle_error_node(state: ExamGenerationState) -> ExamGenerationState:
    """Handles any errors that occurred during the process."""
    # This error is now logged at the node where it occurred.
    # This node is primarily for graph control flow.
    return state

@log_task(agent_name="aggregate_exam_output", task_description="Aggregating all generated exam content into a final structured output.", input_extractor=lambda state: {"query": state.get("query"), "aggregated_item_count": len(state.get("final_generated_content", []))})
def aggregate_final_output_node(state: ExamGenerationState) -> dict:
    """
    Aggregates all generated content and returns it in the state for the parent graph.
    """
    job_id = state['job_id']
    
    try:
        aggregated_output = []
        for content_item in state["final_generated_content"]:
            if isinstance(content_item, dict) and "type" in content_item and "questions" in content_item:
                aggregated_output.append(content_item)
            else:
                aggregated_output.append({"type": "unstructured_content", "content": content_item})

        if state.get("generation_errors"):
            aggregated_output.insert(0, {
                "type": "generation_warnings",
                "message": "Some question types failed to generate. Please check the details below.",
                "errors": state["generation_errors"]
            })
        
        # Determine final job status and update it
        job_status = 'completed'
        if state.get("generation_errors"):
            job_status = 'partial_success' if len(aggregated_output) > 1 else 'failed'
        
        db_logger.update_job_status(job_id, job_status, error_message="Some generation tasks failed." if job_status == 'partial_success' else None)

        existing_title = state.get("main_title")

        # Return the final aggregated content for the decorator to log and for the parent graph to use.
        return {
            "final_generated_content": aggregated_output,
            "main_title": existing_title if existing_title else f"未命名測驗 ({datetime.now().strftime('%Y-%m-%d')})",
            "retrieved_text_chunks": state.get("retrieved_text_chunks", []),  # ✅ 傳遞 RAG chunks 給 parent graph
            "parent_task_id": state.get("current_task_id")  # Propagate parent_task_id for proper task hierarchy
        }

    except Exception as e:
        error_message = f"Error aggregating final output: {str(e)}"
        db_logger.update_job_status(job_id, 'failed', error_message=error_message)
        # Return the error for the decorator to log
        return {"error": error_message, "generation_errors": state.get("generation_errors", []) + [{"task": "aggregate_final_output", "error_message": str(e)}]}