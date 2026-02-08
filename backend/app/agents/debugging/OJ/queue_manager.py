# 檔案: queue_manager.py (修訂版)

import asyncio

class SubmitQueue:
    def __init__(self, max_workers=4): #關鍵：設定最大並發數 (例如 4 個 CPU 核心)
        self.queue = asyncio.Queue()
        self.max_workers = max_workers
        self.running_workers = 0

    async def start_worker(self):
        # 只需要在應用程式啟動時啟動一次即可
        if self.running_workers > 0:
            return
            
        # 創建多個工作線程
        for i in range(self.max_workers):
            asyncio.create_task(self._worker(i))
            self.running_workers += 1
            
        # print(f"SubmitQueue started with {self.max_workers} worker tasks.")

    async def _worker(self, worker_id): # 讓 worker 接受 ID
        while True:
            func, args, fut = await self.queue.get()
            try:
                # print(f"Worker {worker_id} starting task...") # 除錯用
                result = await func(*args) # 這是非阻塞的，可以同時運行多個沙盒任務
                fut.set_result(result)
            except Exception as e:
                fut.set_exception(e)
            finally:
                self.queue.task_done() # 標記任務完成

    async def execute(self, func, *args):
        fut = asyncio.get_event_loop().create_future()
        # 這裡不需要 start_worker，應在應用程式啟動時一次性啟動
        await self.queue.put((func, args, fut))
        # 確保在第一次 execute 之前 worker 已經啟動（如果您的架構需要）
        await self.start_worker() 
        return await fut


submit_queue = SubmitQueue(max_workers=9) 


class AnalysisQueue:
    """
    AI 分析任務佇列：限制同時執行的 AI 分析任務數量，避免 OpenAI Rate Limit。
    與 SubmitQueue 不同，此佇列使用 fire-and-forget 模式，不等待結果。
    """
    def __init__(self, max_workers=5):
        self.queue = asyncio.Queue()
        self.max_workers = max_workers
        self.running_workers = 0
        self._lock = asyncio.Lock()

    async def start_workers(self):
        """啟動 worker tasks（應在應用程式啟動時呼叫一次）"""
        async with self._lock:
            if self.running_workers > 0:
                return
            
            for i in range(self.max_workers):
                asyncio.create_task(self._worker(i))
                self.running_workers += 1

    async def _worker(self, worker_id):
        """Worker 持續從佇列中取出任務並執行"""
        import logging
        logger = logging.getLogger(__name__)
        
        while True:
            func, args, kwargs = await self.queue.get()
            try:
                logger.info(f"AnalysisQueue Worker {worker_id} starting task...")
                await func(*args, **kwargs)
                logger.info(f"AnalysisQueue Worker {worker_id} task completed.")
            except Exception as e:
                logger.error(f"AnalysisQueue Worker {worker_id} task failed: {e}")
            finally:
                self.queue.task_done()

    async def add_task(self, func, *args, **kwargs):
        """
        將任務加入佇列（fire-and-forget 模式）
        
        Args:
            func: 要執行的 async 函數
            *args: 位置參數
            **kwargs: 關鍵字參數
        """
        # await self.start_workers()  # 確保 workers 已啟動
        await self.queue.put((func, args, kwargs))


# 全域 AI 分析佇列實例
analysis_queue = AnalysisQueue(max_workers=15)