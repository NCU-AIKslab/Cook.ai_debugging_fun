from sqlalchemy import Column, Integer, Text, JSON, DateTime, String, Table, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy import and_
from datetime import datetime
import os

# 初始化
Base = declarative_base()
metadata = MetaData()

oj_db_uri = os.getenv("DATABASE_URL")
# 建議加上預設值防呆，或確保環境變數存在
engine = create_engine(oj_db_uri or "postgresql://user:pass@localhost/dbname")
Session = sessionmaker(bind=engine)

# ==========================================
# 1. 使用 Table 定義 (對應你的要求)
# ==========================================
problem_table = Table(
    "problem",
    metadata,
    # 這裡將原本的 _id 與 id 概念統一為 problem_id (String PK)
    Column("problem_id", String, primary_key=True),
    Column("title", Text),
    Column("description", Text),
    Column("input_description", Text),
    Column("output_description", Text),
    Column("samples", JSON),
    Column("create_time", DateTime),
    # 若資料庫中還有判題用的欄位，也可在此補上，例如：
    # Column("test_cases", JSON),
    # Column("time_limit", Integer),
    schema="debugging",     # 指定 schema
    extend_existing=True,   # 允許覆蓋既有定義
)

# ==========================================
# 2. 定義 Problem Class 並映射到 Table
# ==========================================
class Problem(Base):
    __table__ = problem_table

    def to_dict(self):
        return {
            # 這裡統一使用 problem_id (對應前端的 _id)
            "_id": self.problem_id,
            "title": self.title,
            "description": self.description,
            "input_description": self.input_description,
            "output_description": self.output_description,
            "samples": self.samples,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }

# ==========================================
# 3. 查詢邏輯 (欄位名稱已更新為 problem_id)
# ==========================================

def get_problems_by_chapter(chapter_id, start_time=None, end_time=None):
    session = Session()
    try:
        # 默認範圍設定
        if not start_time:
            start_time = "2025-08-14T00:00:00"
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if end_time and isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)
        
        if chapter_id == 'C1':
            # 注意：這裡改用 self.problem_id 或類別屬性 Problem.problem_id
            print('##########', Problem.problem_id)
            
        # 查詢符合條件的題目 (將 _id 改為 problem_id)
        query = session.query(Problem.problem_id, Problem.title, Problem.create_time).filter(
            and_(
                Problem.problem_id.like(f"{chapter_id}_%"),
                Problem.create_time >= start_time,
            )
        )
        
        if end_time:
            query = query.filter(Problem.create_time <= end_time)
            
        problems = query.order_by(Problem.problem_id.asc()).all()
        
        # 返回結果 (將 _id 改為 problem_id)
        return [
            {
                "_id": p.problem_id, 
                "title": p.title, 
                "create_time": p.create_time.isoformat() if p.create_time else None
            } 
            for p in problems
        ]
    finally:
        session.close()

# 透過 Problem.problem_id 查詢題目內容
def get_problem_by_id(problem_id):
    session = Session()
    print("[oj_models.py]進入get_problem_by_id!, problem_id=", problem_id, "type=", type(problem_id))
    try:
        # 查詢符合題號的題目 (將 _id 改為 problem_id)
        problem = session.query(Problem).filter(Problem.problem_id == problem_id).first()
        if not problem:
            return None

        # 將結果轉換為字典
        data = problem.to_dict()

        # 解析 samples 欄位
        data["samples"] = [{"input": s.get("input"), "output": s.get("output")} for s in data.get("samples", [])]

        return data
    finally:
        session.close()

# 舊的 ID 查詢函式 (因為現在主鍵是 String problem_id，建議讓此函式行為與上面一致)
def get_problem_by_problem_id(problem_id):
    # 直接轉發給主查詢函式，避免維護兩套邏輯
    return get_problem_by_id(problem_id)