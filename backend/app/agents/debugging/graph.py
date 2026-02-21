"""
LangGraph Workflow for Debugging Agents
此模組定義了錯誤診斷與引導的 LangGraph 工作流程。
Agent 邏輯已拆分至 coding_help 資料夾中的獨立模組。
"""
import os
import json
import logging
from typing import TypedDict, List, Dict, Any, Literal
from datetime import datetime

# LangChain / LangGraph
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END, START

# 從 coding_help 模組匯入 agent 函式
from backend.app.agents.debugging.coding_help.diagnostic_agent import (
    generate_error_report,
    determine_zpd_level
)
from backend.app.agents.debugging.coding_help.scaffolding_agent import (
    decide_retrieval,
    generate_scaffold_response,
    get_relevant_documents
)
from backend.app.agents.debugging.coding_help.practice_agent import (
    generate_practice_questions
)

# ======================================================
# 1. 環境設定
# ======================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化 LLM
llm = ChatOpenAI(model="gpt-5.1", temperature=0.3)

# ======================================================
# 2. State & Models 定義
# ======================================================
class AgentState(TypedDict):
    student_id: str
    problem_id: str
    current_code: str          
    error_message: str         
    previous_reports: List[Dict] 
    problem_info: Dict[str, str] 
    evidence_report: Dict         
    search_query: str             
    retrieved_docs: List[str]     
    zpd_level: int               
    initial_response: str       
    practice_question: List[Dict]
    is_correct: bool            


class RouteQuery(BaseModel):
    """路由決策結果"""
    datasource: Literal["vector_store", "no_retrieval"]
    search_query: str


# ======================================================
# 3. Agent Nodes (使用 coding_help 模組)
# ======================================================

async def diagnostic_agent(state: AgentState):
    """分析錯誤並對應課程概念 - 呼叫 coding_help.diagnostic_agent"""
    student_id = state.get('student_id')
    problem_id = state.get('problem_id')
    # 生成錯誤報告
    report = await generate_error_report(
        current_code=state['current_code'],
        error_message=state['error_message'],
        problem_info=state['problem_info'],
        student_id=student_id,
        problem_id=problem_id,
    )
    
    # 判斷 ZPD Level
    zpd_result = await determine_zpd_level(
        previous_reports=state['previous_reports'],
        current_report=report,
        student_id=student_id,
        problem_id=problem_id,
    )
    
    return {
        "evidence_report": report,
        "zpd_level": zpd_result["zpd_level"]
    }


async def router_node(state: AgentState):
    """決定是否需要檢索教材 - 呼叫 coding_help.scaffolding_agent"""
    route_result = await decide_retrieval(
        state['evidence_report'],
        student_id=state.get('student_id'),
        problem_id=state.get('problem_id'),
    )
    
    search_query = ""
    if route_result["datasource"] == "vector_store":
        search_query = route_result.get("search_query", "")
    
    return {"search_query": search_query}


async def retrieval_node(state: AgentState):
    """執行教材檢索 - 呼叫 coding_help.scaffolding_agent"""
    docs = get_relevant_documents(state['search_query'])
    return {"retrieved_docs": docs}


async def scaffolding_agent(state: AgentState):
    """引導式教學 (Scaffolding) - 呼叫 coding_help.scaffolding_agent"""
    response = await generate_scaffold_response(
        zpd_level=state['zpd_level'],
        evidence_report=state['evidence_report'],
        problem_info=state['problem_info'],
        current_code=state['current_code'],
        retrieved_docs=state.get('retrieved_docs', []),
        student_id=state.get('student_id'),
        problem_id=state.get('problem_id'),
    )
    
    return {"initial_response": response}


async def practice_agent(state: AgentState):
    """生成鞏固練習題 - 呼叫 coding_help.practice_agent"""
    practice_q = await generate_practice_questions(
        previous_reports=state.get('previous_reports', []),
        problem_info=state.get('problem_info', {}),
        current_report=state.get('evidence_report'),
        student_id=state.get('student_id'),
        problem_id=state.get('problem_id'),
    )
    
    return {"practice_question": practice_q}


# ======================================================
# 4. Graph 建構 (Workflow)
# ======================================================
workflow = StateGraph(AgentState)

workflow.add_node("analyze_code", diagnostic_agent)
workflow.add_node("router", router_node)
workflow.add_node("retrieve", retrieval_node)
workflow.add_node("scaffold_help", scaffolding_agent)
workflow.add_node("generate_practice", practice_agent)


def check_correctness(state: AgentState):
    """判斷是否正確，決定走哪條路"""
    return "generate_practice" if state.get('is_correct') else "analyze_code"


def decide_rag_path(state: AgentState):
    """判斷是否需要檢索"""
    return "retrieve" if state.get("search_query") else "scaffold_help"


workflow.add_conditional_edges(START, check_correctness)
workflow.add_edge("analyze_code", "router")
workflow.add_conditional_edges("router", decide_rag_path, {"retrieve": "retrieve", "scaffold_help": "scaffold_help"})
workflow.add_edge("retrieve", "scaffold_help")
workflow.add_edge("scaffold_help", END)
workflow.add_edge("generate_practice", END)

app_graph = workflow.compile()