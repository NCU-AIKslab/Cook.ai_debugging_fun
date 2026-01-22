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

# Database
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON, DateTime, select, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

# ======================================================
# 1. 環境設定與資料庫連接
# ======================================================

# 設定 Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 資料庫連線 (使用您提供的資訊)
# 建議將密碼設為環境變數，或在此處直接使用
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg2://kslab:Kslab35356!@cookaidb.czeeey0q2dkq.ap-northeast-1.rds.amazonaws.com:5432/cookai"
)

# RAG 參數設定
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# 初始化資料庫連線
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# 定義 ORM 模型 (用於檢索)
class DocumentChunk(Base):
    __tablename__ = 'document_chunks'
    __table_args__ = {'schema': 'debugging'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    unique_content_id = Column(Integer, nullable=False)
    chunk = Column(Text, nullable=False)
    chunk_order = Column(Integer, nullable=False)
    chunk_metadata = Column('metadata', JSON, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 初始化 LLM 與 Embedding
# 請確保環境變數 OPENAI_API_KEY 已設定
llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

# ======================================================
# 2. State (狀態) 定義
# ======================================================
class AgentState(TypedDict):
    # --- Inputs (輸入) ---
    student_id: str
    problem_id: str
    current_code: str          
    error_message: str         
    previous_reports: List[Dict] 
    problem_info: Dict[str, str] 
    
    # --- Process Data (過程資料) ---
    evidence_report: Dict         # 診斷報告
    search_query: str             # Router 決定的搜尋關鍵字
    retrieved_docs: List[str]     # RAG 檢索回來的教材內容
    
    # --- Outputs (輸出) ---
    zpd_level: int               
    initial_response: str       
    practice_question: List[Dict]
    
    # --- Flow Control (流程控制) ---
    is_correct: bool            

# ======================================================
# 3. 核心功能函式 (Retriever & Tools)
# ======================================================

def get_relevant_documents(query: str, top_k: int = 3) -> List[str]:
    """
    執行向量搜尋：從 PostgreSQL 找尋最相關的教材 Chunk
    """
    if not query or not query.strip():
        return []
    
    session = SessionLocal()
    try:
        # 1. 將搜尋語句轉為向量
        query_vector = embeddings.embed_query(query)
        
        # 2. 資料庫向量相似度搜尋 (Cosine Distance)
        stmt = select(DocumentChunk).order_by(
            DocumentChunk.embedding.cosine_distance(query_vector)
        ).limit(top_k)
        
        results = session.execute(stmt).scalars().all()
        
        docs = []
        for row in results:
            # 整理教材內容與 Metadata (如頁碼)
            page_info = row.chunk_metadata.get('page_numbers', [])
            doc_text = f"[教材內容 (頁碼: {page_info})]: {row.chunk}"
            docs.append(doc_text)
            
        return docs
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        return []
    finally:
        session.close()

# Router 的結構化輸出定義
class RouteQuery(BaseModel):
    """路由決策模型：決定下一步是檢索教材還是直接回答。"""
    datasource: Literal["vector_store", "no_retrieval"] = Field(
        ...,
        description="若錯誤涉及邏輯觀念或不熟悉的語法，選擇 'vector_store'。若僅是簡單語法拼寫錯誤，選擇 'no_retrieval'。"
    )
    search_query: str = Field(
        ...,
        description="若選擇 'vector_store'，請生成搜尋關鍵字。若選擇 'no_retrieval'，請留空。"
    )

# ======================================================
# 4. Agent Nodes (節點邏輯)
# ======================================================

# --- Node 1: Diagnostic Agent ---
async def diagnostic_agent(state: AgentState):
    print("--- Node: Diagnostic Agent ---")
    code = state['current_code']
    error = state['error_message']
    
    prompt = f"""
    你是一位 Python 程式設計導師。請分析以下的學生程式碼與錯誤訊息。
    請提供一個結構化的 JSON 輸出。

    程式碼:
    {code}

    錯誤訊息:
    {error}

    請務必僅回傳 JSON 格式：
    {{
        "error_type": "Syntax (語法錯誤) / Logic (邏輯錯誤) / Runtime (執行錯誤)",
        "location": "行號或區塊",
        "misconception": "簡短解釋學生誤解了什麼觀念 (繁體中文)",
        "severity": "High/Medium/Low"
    }}
    """
    response = await llm.ainvoke([
        SystemMessage(content="You are a strict code analyzer. JSON only."), 
        HumanMessage(content=prompt)
    ])
    
    try:
        content = response.content.replace("```json", "").replace("```", "").strip()
        report = json.loads(content)
    except:
        report = {"error_type": "Unknown", "misconception": "解析失敗", "severity": "Low"}
        
    return {"evidence_report": report}

# --- Node 2: Router Agent ---
async def router_node(state: AgentState):
    print("--- Node: Router Agent ---")
    report = state['evidence_report']
    
    structured_llm_router = llm.with_structured_output(RouteQuery)
    
    system_prompt = """你是一位程式教學路由專家。
    請根據學生的錯誤診斷報告，判斷是否需要查閱知識庫(RAG)來輔助教學。
    1. 不需要查閱 (no_retrieval): 單純打字錯誤、縮排錯誤、變數拼錯。
    2. 需要查閱 (vector_store): 觀念不清、誤用函式、邏輯錯誤、對語法不熟悉。
    """
    
    user_prompt = f"Error Type: {report.get('error_type')}\nMisconception: {report.get('misconception')}"
    
    result = await structured_llm_router.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    search_q = result.search_query if result.datasource == "vector_store" else ""
    return {"search_query": search_q}

# --- Node 3: Retrieval Agent ---
async def retrieval_node(state: AgentState):
    query = state['search_query']
    print(f"--- Node: Retrieval Agent (Query: {query}) ---")
    docs = get_relevant_documents(query)
    return {"retrieved_docs": docs}

# --- Node 4: Scaffolding Agent ---
async def scaffolding_agent(state: AgentState):
    print("--- Node: Scaffolding Agent ---")
    
    current_report = state['evidence_report']
    past_reports = state['previous_reports']
    current_code = state['current_code']
    retrieved_docs = state.get('retrieved_docs', [])
    print(retrieved_docs)
    
    # 計算 ZPD
    current_type = current_report.get("error_type")
    repeat_count = sum(1 for rep in past_reports if rep.get("error_type") == current_type)
    
    if repeat_count >= 2:
        zpd, strategy = 1, "明確解釋錯誤與修復方式，但不要直接給代碼。"
    elif repeat_count == 1:
        zpd, strategy = 2, "指出錯誤位置並給予引導式提問。"
    else:
        zpd, strategy = 3, "僅給予概念性提示。"

    # 組合 Prompt
    rag_context = ""
    if retrieved_docs:
        rag_context = "\n--- 參考教材 (Reference Material) ---\n" + "\n".join(retrieved_docs) + "\n(請根據上述教材內容輔助解釋)\n"
    
    prompt = f"""
    你是程式導師。請根據診斷與教材生成引導。
    
    診斷: {current_report}
    程式碼: {current_code}
    {rag_context}
    
    策略 (ZPD {zpd}): {strategy}
    請用繁體中文回答，語氣鼓勵。
    """
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"zpd_level": zpd, "initial_response": response.content}

# --- Node 5: Practice Agent ---
async def practice_agent(state: AgentState):
    print("--- Node: Practice Generator ---")
    
    # 1. 檢查是否有錯誤紀錄
    past_reports = state.get('previous_reports', [])
    
    # 過濾出有效的錯誤報告 (排除空值或無效資料)
    valid_errors = [
        r for r in past_reports 
        if r and isinstance(r, dict) and r.get('error_type') and r.get('misconception')
    ]
    
    # [關鍵邏輯] 若沒有錯誤紀錄 (代表一次 AC 或無重大觀念錯誤)，則不生成練習題
    if not valid_errors:
        print("  -> No error history found (One-shot AC). Skipping practice generation.")
        return {"practice_question": []}

    print(f"  -> Found {len(valid_errors)} error reports. Generating targeted practice...")

    # 2. 準備 Context (題目與錯誤歷史)
    prob_info = state.get('problem_info', {})
    problem_context = f"""
    題目名稱: {prob_info.get('title', 'N/A')}
    題目描述: {prob_info.get('description', 'N/A')}
    輸入說明: {prob_info.get('input_description', 'N/A')}
    輸出說明: {prob_info.get('output_description', 'N/A')}
    """

    # 將錯誤歷史轉為 JSON 字串，供 LLM 分析歸納
    history_json = json.dumps(valid_errors, ensure_ascii=False, indent=2)

    # 3. 建構 Prompt (只針對錯誤痛點出題)
    prompt = f"""
    學生在此題目中經歷了錯誤嘗試，但現在已成功通過。
    請扮演一位程式導師，根據下方的「學生錯誤歷史紀錄」，針對其**最核心的觀念誤區**生成 **1 題** 選擇題，幫助學生鞏固觀念。

    --- 題目資訊 ---
    {problem_context}

    --- 學生錯誤歷史紀錄 (由舊到新) ---
    {history_json}

    --- 生成規則 ---
    1. **針對性**: 題目必須直接關聯到上述紀錄中的錯誤 (例如：若常犯邊界錯誤，就出一題關於 range 範圍的題目)。
    2. **情境化**: 請結合本題的程式碼情境或類似的簡短範例。
    3. **格式**: 務必回傳 **JSON Array**。
    4. **語言**: 繁體中文。

    --- JSON 範例 ---
    [
        {{
            "id": "Q1",
            "type": "logic", 
            "question": {{
                "text": "在您之前的提交中，常誤用 'if' 來處理重複動作。請問若要讓程式重複執行直到條件滿足，應使用哪個關鍵字？",
                "code": {{ "content": "count = 0\\n# 這裡該填什麼？\\n... count < 5:\\n    print(count)\\n    count += 1", "language": "python" }}
            }},
            "options": [
                {{ "id": 1, "label": "if", "feedback": "錯誤。if 只會執行一次判斷。" }},
                {{ "id": 2, "label": "while", "feedback": "正確！while 會重複執行直到條件為 False。" }}
            ],
            "answer_config": {{ "correct_id": 2, "explanation": "While 迴圈是用於重複執行的結構。" }}
        }}
    ]
    """

    # 4. 呼叫 LLM 生成
    try:
        response = await llm.ainvoke([
            SystemMessage(content="You are an expert Computer Science Education specialist. Output JSON only."),
            HumanMessage(content=prompt)
        ])
        
        clean_content = response.content.replace("```json", "").replace("```", "").strip()
        practice_q_list = json.loads(clean_content)
        
        if isinstance(practice_q_list, dict):
            practice_q_list = [practice_q_list]
            
    except Exception as e:
        print(f"  -> Practice Generation Failed: {e}")
        practice_q_list = []

    return {"practice_question": practice_q_list}

# ======================================================
# 5. Graph 建構 (Workflow Definition)
# ======================================================

workflow = StateGraph(AgentState)

# 1. 加入節點
workflow.add_node("analyze_code", diagnostic_agent)
workflow.add_node("router", router_node)
workflow.add_node("retrieve", retrieval_node)
workflow.add_node("scaffold_help", scaffolding_agent)
workflow.add_node("generate_practice", practice_agent)

# 2. 定義條件邏輯
def check_correctness(state: AgentState):
    if state.get('is_correct'):
        return "generate_practice"
    return "analyze_code"

def decide_rag_path(state: AgentState):
    query = state.get("search_query")
    if query and len(query.strip()) > 0:
        return "retrieve"      # 走 RAG 路徑
    return "scaffold_help"     # 走直接生成路徑

# 3. 連接邊
workflow.add_conditional_edges(
    START,
    check_correctness,
    {"generate_practice": "generate_practice", "analyze_code": "analyze_code"}
)

workflow.add_edge("analyze_code", "router")

workflow.add_conditional_edges(
    "router",
    decide_rag_path,
    {"retrieve": "retrieve", "scaffold_help": "scaffold_help"}
)

workflow.add_edge("retrieve", "scaffold_help")
workflow.add_edge("scaffold_help", END)
workflow.add_edge("generate_practice", END)

# 4. 編譯圖
app_graph = workflow.compile()