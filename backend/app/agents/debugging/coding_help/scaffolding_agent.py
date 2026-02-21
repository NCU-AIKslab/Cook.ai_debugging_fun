"""
Scaffolding Agent 模組
功能：
1. Router Agent：判斷是否需要檢索教材 (RAG)
2. Scaffolding Agent：依據 ZPD Level 生成引導式回覆
"""
import os
import json
import logging
from typing import TypedDict, List, Dict, Any, Literal

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, Text, JSON
from pgvector.sqlalchemy import Vector
from backend.app.agents.debugging.db import save_llm_charge

logger = logging.getLogger(__name__)

# 資料庫連接
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


# 初始化 LLM (增加逾時與重試設定以提升穩定性)
llm = ChatOpenAI(model="gpt-5.1", temperature=0.3, request_timeout=120, max_retries=3)
llm2 = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, request_timeout=120, max_retries=3)
embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)


class RouteQuery(BaseModel):
    """路由決策結果"""
    datasource: Literal["vector_store", "no_retrieval"] = Field(
        description="決定是否需要檢索教材"
    )
    search_query: str = Field(
        description="若需要檢索，提供搜尋查詢語句"
    )
    reasoning: str = Field(
        description="決策理由"
    )


def get_relevant_documents(query: str, top_k: int = 3) -> List[str]:
    """
    從向量資料庫檢索相關教材
    """
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


async def decide_retrieval(
    evidence_report: Dict[str, Any],
    student_id: str = None,
    problem_id: str = None,
) -> Dict[str, Any]:
    """
    獨立的 Router Agent：判斷是否需要檢索教材
    
    Args:
        evidence_report: 錯誤診斷報告
        
    Returns:
        包含 datasource, search_query, reasoning 的決策結果
    """
    misconception = evidence_report.get("misconception", "")
    error_type = evidence_report.get("error_type", "")
    
    prompt = f"""
    你是一位教學資源規劃專家。請判斷學生的錯誤是否需要參考教材來輔助解釋。
    
    【學生錯誤資訊】
    錯誤類型: {error_type}
    誤解觀念: {misconception}
    
    【判斷準則】
    - 選擇 "vector_store"：若錯誤涉及觀念理解問題，需要教材輔助解釋
    - 選擇 "no_retrieval"：若為簡單打字錯誤、語法遺漏等不需要觀念說明的問題
    
    請輸出 JSON:
    {{
        "datasource": "vector_store" 或 "no_retrieval",
        "search_query": "若選擇 vector_store，請提供搜尋關鍵字；否則留空",
        "reasoning": "決策理由"
    }}
    """
    
    try:
        response = await llm2.ainvoke([
            SystemMessage(content="你是教學資源規劃專家。請只輸出 JSON。"),
            HumanMessage(content=prompt)
        ])
        
        content = response.content.replace("```json", "").replace("```", "").strip()
        result = json.loads(content)
        # 記錄 token 用量
        if student_id:
            usage = response.response_metadata.get("token_usage", {})
            details = usage.get("prompt_tokens_details") or {}
            save_llm_charge(
                student_id=student_id,
                usage_type="code_correction",
                model_name="gpt-4o-mini",
                input_tokens=usage.get("prompt_tokens", 0),
                cached_input_tokens=details.get("cached_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                problem_id=problem_id,
            )
        return {
            "datasource": result.get("datasource", "no_retrieval"),
            "search_query": result.get("search_query", ""),
            "reasoning": result.get("reasoning", "")
        }
        
    except Exception as e:
        logger.error(f"Router decision failed: {e}")
        return {
            "datasource": "no_retrieval",
            "search_query": "",
            "reasoning": f"決策失敗: {str(e)}"
        }


async def generate_scaffold_response(
    zpd_level: int,
    evidence_report: Dict[str, Any],
    problem_info: Dict[str, str],
    current_code: str,
    retrieved_docs: List[str] = None,
    student_id: str = None,
    problem_id: str = None,
) -> str:
    """
    依據 ZPD Level 生成引導式回覆
    
    Args:
        zpd_level: ZPD 等級 (1-3)
        evidence_report: 錯誤診斷報告
        problem_info: 題目資訊
        current_code: 學生程式碼
        retrieved_docs: 檢索到的教材 (可選)
        
    Returns:
        引導式回覆文字
    """
    # 根據 ZPD 等級決定教學策略
    strategies = {
        1: "引導學生思考修正邏輯，可提供部分範例程式碼片段。",
        2: "給予具體提示，指出錯誤方向但不直接給答案。",
        3: "僅給予方向性提示，讓學生自行思考和探索。"
    }
    strategy = strategies.get(zpd_level, strategies[3])
    
    rag_context = "\n".join(retrieved_docs) if retrieved_docs else "無相關教材"
    
    prompt = f"""
    你是一位專業且耐心的 Python 老師。請針對學生的錯誤提供引導。
    
    程式題目: {json.dumps(problem_info, ensure_ascii=False)}
    **注意**: 輸出格式需參考 samples
    
    學生程式碼: 
    ```python
    {current_code}
    ```
    
    診斷結果: {evidence_report.get('misconception', '無')}
    參考教材: {rag_context}
    
    【教學策略 (ZPD 等級 {zpd_level})】: {strategy}
    
    請遵守：
    1. 使用繁體中文，**簡單明瞭字數100字內**，條列式回覆，不帶任何情緒。
    2. 不要給學生參考教材來源資訊(例如：可參考C1 PPT第X頁)。
    3. 嚴禁使用 Markdown 語法 (不要使用 **, #, ` 等符號)。
    4. 依照策略強度提供引導，不要直接給出完整正確答案。
    5. 回覆應該是 2-4 個條列式重點。
    """
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        # 記錄 token 用量
        if student_id:
            usage = response.response_metadata.get("token_usage", {})
            details = usage.get("prompt_tokens_details") or {}
            save_llm_charge(
                student_id=student_id,
                usage_type="code_correction",
                model_name="gpt-5.1",
                input_tokens=usage.get("prompt_tokens", 0),
                cached_input_tokens=details.get("cached_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                problem_id=problem_id,
            )
        return response.content
        
    except Exception as e:
        logger.error(f"Scaffold generation failed: {e}")
        return "系統無法生成引導，請修改程式碼再試一次。"


async def run_scaffolding(
    zpd_level: int,
    evidence_report: Dict[str, Any],
    problem_info: Dict[str, str],
    current_code: str,
    student_id: str = None,
    problem_id: str = None,
) -> Dict[str, Any]:
    """
    執行完整 Scaffolding 流程
    
    Returns:
        包含 response 和 retrieved_docs 的結果
    """
    # Step 1: 決定是否需要檢索
    route_result = await decide_retrieval(evidence_report, student_id=student_id, problem_id=problem_id)
    
    # Step 2: 執行檢索 (如果需要)
    retrieved_docs = []
    if route_result["datasource"] == "vector_store" and route_result["search_query"]:
        retrieved_docs = get_relevant_documents(route_result["search_query"])
    
    # Step 3: 生成引導式回覆
    response = await generate_scaffold_response(
        zpd_level=zpd_level,
        evidence_report=evidence_report,
        problem_info=problem_info,
        current_code=current_code,
        retrieved_docs=retrieved_docs,
        student_id=student_id,
        problem_id=problem_id,
    )
    
    return {
        "response": response,
        "retrieved_docs": retrieved_docs,
        "route_reasoning": route_result.get("reasoning", "")
    }
