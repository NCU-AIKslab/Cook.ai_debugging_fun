from langchain_core.messages import SystemMessage, HumanMessage

from backend.app.agents.teacher_agent.state import TeacherAgentState
from backend.app.utils.db_logger import log_task
# Import helpers from the exam_generator skill, as they are generic enough
from backend.app.agents.teacher_agent.skills.exam_generator.exam_nodes import get_llm, MODEL_PRICING

@log_task(agent_name="general_chat_skill", task_description="Handle general conversation and provide intelligent fallback.", input_extractor=lambda state: {"user_query": state.get("user_query")})
def general_chat_node(state: TeacherAgentState) -> dict:
    """
    An intelligent fallback node that uses an LLM to provide a helpful response
    when no other skill can handle the request. It informs the user about the
    agent's limitations and suggests available skills.
    """
    user_query = state.get("user_query", "")

    TITLE_SEPARATOR = "|||TITLE_END|||"

    # 根據對話內容動態生成title
    system_prompt = (
        "You are a helpful and polite AI teaching assistant, speaking in Traditional Chinese (繁體中文). "
        "Your primary goal is to manage user expectations and guide them towards the agent's capabilities. "
        "You MUST start your response with a short, descriptive title (5-10 words) for the conversation, followed immediately by the separator '{sep}' (without quotes), and then the main message content."
    ).format(sep=TITLE_SEPARATOR)
    
    human_prompt = (
        f"A user just said: '{user_query}'.\n\n"
        "You are an AI teaching assistant. Your current capabilities include: \n"
        "1. Generating exams (生成考卷) based on provided materials. \n"
        "2. Summarizing course materials (總結教材) from provided documents. \n"
        "You should respond by introducing your capabilities in Traditional Chinese, "
        "and then invite the user to ask for one of these services. "
        "Avoid directly stating what you *cannot* do unless the user explicitly asks for an unavailable feature. "
        "For example: '您好！我是一位 AI 教學助理。目前我可以根據您提供的資料生成考卷，或是為您總結教材內容。請問您需要哪方面的協助呢？'"
    )

    try:
        llm = get_llm()
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
        
        response = llm.invoke(messages)
        raw_response = response.content

        if TITLE_SEPARATOR in raw_response:
            title_part, content_part = raw_response.split(TITLE_SEPARATOR, 1)
            ai_response_title = title_part.strip()
            ai_response_content = content_part.strip()
        else:
            # Fallback if LLM misses the separator
            ai_response_title = "Cook AI 助教回覆"
            ai_response_content = raw_response

        token_usage = response.response_metadata.get("token_usage", {})
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        model_name = llm.model_name
        pricing = MODEL_PRICING.get(model_name, {"input": 0, "output": 0})
        estimated_cost = ((prompt_tokens / 1_000_000) * pricing["input"]) + ((completion_tokens / 1_000_000) * pricing["output"])

        final_result = {
            "type": "message",
            "title": ai_response_title,
            "content": ai_response_content
        }

        return {
            "final_result": final_result,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": estimated_cost,
            "model_name": model_name,
            "parent_task_id": state.get("current_task_id")  # Propagate parent_task_id for proper task hierarchy
        }

    except Exception as e:
        print(f"Error in general_chat_node: {e}")
        # Fallback to a simple hardcoded response in case of LLM failure
        final_result = {
            "type": "message",
            "title": "Cook AI 助教回覆",
            "content": "抱歉，我目前遇到一些問題，暫時無法回覆您。請稍後再試。"
        }
        return {"final_result": final_result, "error": str(e)}

