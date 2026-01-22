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