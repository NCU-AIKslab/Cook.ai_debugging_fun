import os
from sqlalchemy import create_engine, MetaData, Table, inspect,  insert
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

try:
    metadata = MetaData()
    user_info_table = Table('user_info', metadata, autoload_with=engine, schema='debugging')

    with engine.connect() as conn:
        print("\nAttempting insert with semester...")
        
        stmt = insert(user_info_table).values(
            stu_id="debug_test_003",
            stu_name="Debug User 3",
            stu_pwd="nopassword",
            semester="114-1",
            is_teacher=False
        )
        conn.execute(stmt)
        conn.commit()
        print("Insert successful.")

except Exception as e:
    print(f"\nError: {e}")
