import os
import json
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from backend.app.agents.rag_agent import rag_agent
from backend.app.utils import db_logger
from backend.app.utils.db_logger import log_task, log_task_sources
from backend.app.agents.teacher_agent.skills.exam_generator.exam_nodes import MODEL_PRICING, get_llm, _prepare_multimodal_content

from .state import SummarizationState

# --- Pydantic Models for Structured Summary Output ---
class SummarySection(BaseModel):
    section_title: str = Field(..., description="The title of the summary section.")
    content_list: List[str] = Field(..., description="A list of key points or sentences for this section.")

class SummaryReport(BaseModel):
    title: str = Field(..., description="The main title of the summary report.")
    sections: List[SummarySection] = Field(..., description="A list of sections, each with a title and key points.")

# --- Node Functions ---

@log_task(agent_name="retriever", task_description="Retrieve relevant document chunks for summarization.", input_extractor=lambda state: {"query": state.get("query"), "unique_content_id": state.get("unique_content_id")})
def retrieve_chunks_node(state: SummarizationState) -> dict:
    """
    Retrieves context using RAGAgent and populates the state.
    """
    try:
        rag_results = rag_agent.search(user_prompt=state["query"], unique_content_id=state["unique_content_id"])
        # The decorator has already created the task and injected its ID into the state
        log_task_sources(state["current_task_id"], rag_results["text_chunks"])

        return {
            "retrieved_page_content": rag_results["page_content"],
            "parent_task_id": state["current_task_id"] # Set self as parent for the next node
        }
    except Exception as e:
        return {"error": f"Failed to retrieve context: {str(e)}"}

@log_task(
    agent_name="summarizer",
    task_description="Summarize provided course material.",
    input_extractor=lambda state: {
        "query": state.get("query"),
        "unique_content_id": state.get("unique_content_id"),
        "retrieved_pages": len(state.get("retrieved_page_content", []))
    }
)
def summarize_node(state: SummarizationState) -> dict:
    """
    Generates a structured summary based on content already in the state,
    and saves it to the database.
    """
    try:
        # 1. Get retrieved content from state
        retrieved_page_content = state.get("retrieved_page_content")

        if not retrieved_page_content:
            raise ValueError("No content found in state for summarization.")

        combined_text, image_data_urls = _prepare_multimodal_content(retrieved_page_content)

        if not combined_text and not image_data_urls:
            raise ValueError("No text or images extracted from the document for summarization.")

        # 2. Construct LLM Prompt for Tool Calling
        llm = get_llm()
        
        system_prompt = (
            "You are an expert educational assistant. Your task is to summarize the provided course material "
            "into a a structured summary report. Focus on key concepts, main ideas, and important details. "
            "The summary should be suitable for students or teachers to quickly grasp the essence of the material. "
            "You MUST use the `SummaryReport` tool to output the summary. "
            "Respond in Traditional Chinese (繁體中文)."
        )
        
        human_message_content = [
            {"type": "text", "text": f"**--- COURSE MATERIAL FOR SUMMARIZATION ---**\n"},
            {"type": "text", "text": f"{combined_text}\n"},
            {"type": "text", "text": f"\n**--- INSTRUCTIONS ---**\n"},
            {"type": "text", "text": f"Please provide a comprehensive yet concise summary of the above material. "
                                      f"Ensure the summary is well-structured with a main title and distinct sections, "
                                      f"each containing a list of key points. "
                                      f"The summary should be in Traditional Chinese. "
                                      f"You MUST use the `SummaryReport` tool to format your response."}
        ]

        if image_data_urls:
            for image_uri in image_data_urls:
                human_message_content.append({
                    "type": "image_url",
                    "image_url": {"url": image_uri, "detail": "low"}
                })

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message_content)
        ]

        # 3. Call LLM with Tool Calling
        summarizer_llm = llm.bind_tools(tools=[SummaryReport], tool_choice={"type": "function", "function": {"name": "SummaryReport"}})
        response = summarizer_llm.invoke(messages)
        
        if not response.tool_calls:
            raise ValueError("The summarizer model did not call the required 'SummaryReport' tool.")
            
        # Parse the structured summary
        summary_report = SummaryReport(**response.tool_calls[0]['args'])
        
        # 4. Extract token usage and cost
        token_usage = response.response_metadata.get("token_usage", {})
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        model_name = llm.model_name
        pricing = MODEL_PRICING.get(model_name, {"input": 0, "output": 0})
        estimated_cost = ((prompt_tokens / 1_000_000) * pricing["input"]) + ((completion_tokens / 1_000_000) * pricing["output"])

        # 5. Return the summary report for the parent graph to handle.
        # The @log_task decorator will capture this return value as the node's output.
        summary_report_dict = summary_report.model_dump()

        final_generated_content = {
            "type": "summary",
            **summary_report_dict
        }
        
        return {
            "final_generated_content": final_generated_content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": estimated_cost,
            "model_name": model_name,  # Add model_name
            "parent_task_id": state.get("current_task_id")  # Propagate parent_task_id for proper task hierarchy
        }

    except Exception as e:
        error_message = f"Failed to generate structured summary: {str(e)}"
        return {
            "error": error_message,
            "final_generated_content": None
        }
