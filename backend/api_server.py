from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# Import routers
from backend.app.routers import auth_router
from backend.app.routers import debugging
from backend.app.routers import dashboard 
from backend.app.routers import teacher_problem
# Import queues for initialization
from backend.app.agents.debugging.OJ.queue_manager import analysis_queue

# --- FastAPI App ---

# Create the FastAPI app
app = FastAPI(
    title="Cook.ai API Server",
    description="API for ingesting documents and generating educational materials.",
    root_path="/debugging-backend",
)

# --- Add CORS Middleware ---
origins = [
    "http://localhost:3001",
    "http://140.115.54.162:3001",
    "http://140.115.54.167:3001",
    "http://cookai-debugging-lab.moocs.tw:3001",
    "http://cookai-debugging-lab.moocs.tw",
    "https://cookai-debugging-lab.moocs.tw:3001",
    "https://cookai-debugging-lab.moocs.tw",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Startup Event: Initialize Background Queues ---
@app.on_event("startup")
async def startup_event():
    """
    Initialize background task queues when the server starts.
    This ensures AI analysis workers are ready to process tasks.
    """
    await analysis_queue.start_workers()
    print(f"✅ AnalysisQueue initialized with {analysis_queue.max_workers} workers.")

# --- Root, Health Check ---

@app.get("/", include_in_schema=False)
def read_root():
    """
    Redirects the root URL to the API documentation.
    """
    return RedirectResponse(url="/docs")

@app.get("/health", tags=["System"])
def health_check():
    """
    A simple health check endpoint that returns the server status.
    """
    return {"status": "ok"}

# Debugging router (程式輔助系統)
app.include_router(debugging.router)

# Auth router (認證系統)
app.include_router(auth_router.router)

# Dashboard router (教師儀表板)
# Dashboard router (教師儀表板)
app.include_router(dashboard.router)

# Teacher Problem Management Router (題目生成與設定)
app.include_router(teacher_problem.router)

# To run this server:
# 1. Make sure you are in the root directory of the project (Cook.ai).
# 2. Run the command: uvicorn backend.api_server:app --reload --port 8000
