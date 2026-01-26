import os
import json
import logging
import re
from typing import TypedDict, List, Dict, Any, Literal
from datetime import datetime

# LangChain / LangGraph
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END, START

# Database
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON, DateTime, select
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

# ======================================================
# 1. 環境設定與資料庫連接
# ======================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg2://kslab:Kslab35356!@cookaidb.czeeey0q2dkq.ap-northeast-1.rds.amazonaws.com:5432/cookai"
)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class DocumentChunk(Base):
    __tablename__ = 'document_chunks'
    __table_args__ = {'schema': 'debugging'}
    id = Column(Integer, primary_key=True)
    chunk = Column(Text, nullable=False)
    chunk_metadata = Column('metadata', JSON, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)

# 初始化 LLM (模仿 recommendation_bp 使用 gpt-4o)
llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

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
    datasource: Literal["vector_store", "no_retrieval"]
    search_query: str

# ======================================================
# 3. 核心工具函式
# ======================================================
def get_relevant_documents(query: str, top_k: int = 3) -> List[str]:
    if not query or not query.strip():
        return []
    session = SessionLocal()
    try:
        query_vector = embeddings.embed_query(query)
        stmt = select(DocumentChunk).order_by(
            DocumentChunk.embedding.cosine_distance(query_vector)
        ).limit(top_k)
        results = session.execute(stmt).scalars().all()
        return [f"[教材內容]: {row.chunk}" for row in results]
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        return []
    finally:
        session.close()

# ======================================================
# 4. Agent Nodes (重構重點)
# ======================================================

async def diagnostic_agent(state: AgentState):
    """分析錯誤並對應課程概念"""
    prompt = f"""
    你是一位專業的 Python 教學助理。請分析學生的錯誤並輸出 JSON。
    程式題目: {state['problem_info']}
    學生程式碼: {state['current_code']}
    程式碼錯誤訊息: {state['error_message']}

    格式規範:
    {{
        "error_type": "Syntax (語法錯誤) / Logic (邏輯錯誤) / Runtime (執行錯誤)",
        "location": "行號或區塊",
        "misconception": "詳細解釋學生誤解的觀念 (繁體中文)",
        "severity": "High/Medium/Low"
    }}
    """
    response = await llm.ainvoke([SystemMessage(content="JSON only."), HumanMessage(content=prompt)])
    try:
        report = json.loads(response.content.replace("```json", "").replace("```", ""))
    except:
        report = {"error_type": "Unknown", "misconception": "解析失敗"}
    return {"evidence_report": report}

async def router_node(state: AgentState):
    structured_llm_router = llm.with_structured_output(RouteQuery)
    user_prompt = f"錯誤描述: {state['evidence_report'].get('misconception')}"
    result = await structured_llm_router.ainvoke([
        SystemMessage(content="判斷是否需要檢索教材。觀念問題選 vector_store，打字錯誤選 no_retrieval。"),
        HumanMessage(content=user_prompt)
    ])
    return {"search_query": result.search_query if result.datasource == "vector_store" else ""}

async def retrieval_node(state: AgentState):
    docs = get_relevant_documents(state['search_query'])
    return {"retrieved_docs": docs}

async def scaffolding_agent(state: AgentState):
    """引導式教學 (Scaffolding)"""
    report = state['evidence_report']
    # 根據錯誤次數決定 ZPD 等級
    repeat_count = sum(1 for rep in state['previous_reports'] if rep.get("error_type") == report.get("error_type"))
    zpd, strategy = (1, "引導學生思考修正邏輯，可提供部分範例。") if repeat_count >= 2 else (2, "給予具體提示。") if repeat_count == 1 else (3, "僅給予方向性提示。")

    rag_context = "\n".join(state.get('retrieved_docs', []))
    prompt = f"""
    你是一位專業且耐心的 Python 老師。請針對學生的錯誤提供引導。
    
    程式題目: {state['problem_info']} **注意**:輸出格式需參考sampls
    學生程式碼: {state['current_code']}
    診斷結果: {report.get('misconception')}
    參考教材: {rag_context}
    
    【教學策略 (ZPD 等級 {zpd})】: {strategy}
    
    請遵守：
    1. 使用繁體中文，**簡單明瞭**，條列式回覆，不帶任何情緒。
    2. 嚴禁使用 Markdown 語法。
    3. 依照策略強度提供引導，不要直接給出完整正確答案。
    """
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"zpd_level": zpd, "initial_response": response.content}

async def practice_agent(state: AgentState):
    """生成鞏固練習題"""
    valid_errors = [r for r in state.get('previous_reports', []) if r]
    if not valid_errors and not state.get('is_correct'):
        return {"practice_question": []}

    prob_info = state.get('problem_info', {})
    prompt = f"""
    請根據學生之前的錯誤，設計 1 題「單選題」來鞏固觀念。
    
    題目目標: {prob_info}
    學生弱點: {state['evidence_report'].get('misconception')}
    
    【生成規範】:
    1. 題目敘述請用自然語言，避免直接寫出 Python 語法（例如：不要寫「使用 split()」，改寫「將字串以空格拆分」）。
    2. 需給出**完整程式碼**，並在填空處用 "_____" 表示。
    3. 提供 3 個選項，正確答案隨機分佈。
    4. 每個選項需包含 feedback (回饋)。
    
    格式規範 (JSON Array):
    [
        {{
            "id": "Q1",
            "type": "logic", 
            "question": {{
                "text": "題目描述",
                "code": {{ "content": "```python\\n<帶有錯誤的完整程式碼>\\n```", "language": "python" }}
            }},
            "options": [
                {{ "id": 1, "label": "選項A", "feedback": "❌ 錯誤原因..." }},
                {{ "id": 2, "label": "選項A", "feedback": "❌ 錯誤原因..." }}
            ],
            "answer_config": {{ "correct_id": 2, "explanation": "詳解..." }}
        }}
    ]
    """
    response = await llm.ainvoke([SystemMessage(content="JSON only."), HumanMessage(content=prompt)])
    try:
        practice_q = json.loads(response.content.replace("```json", "").replace("```", ""))
        return {"practice_question": practice_q if isinstance(practice_q, list) else [practice_q]}
    except:
        return {"practice_question": []}

# ======================================================
# 5. Graph 建構 (Workflow)
# ======================================================
workflow = StateGraph(AgentState)

workflow.add_node("analyze_code", diagnostic_agent)
workflow.add_node("router", router_node)
workflow.add_node("retrieve", retrieval_node)
workflow.add_node("scaffold_help", scaffolding_agent)
workflow.add_node("generate_practice", practice_agent)

def check_correctness(state: AgentState):
    return "generate_practice" if state.get('is_correct') else "analyze_code"

def decide_rag_path(state: AgentState):
    return "retrieve" if state.get("search_query") else "scaffold_help"

workflow.add_conditional_edges(START, check_correctness)
workflow.add_edge("analyze_code", "router")
workflow.add_conditional_edges("router", decide_rag_path, {"retrieve": "retrieve", "scaffold_help": "scaffold_help"})
workflow.add_edge("retrieve", "scaffold_help")
workflow.add_edge("scaffold_help", END)
workflow.add_edge("generate_practice", END)

app_graph = workflow.compile()