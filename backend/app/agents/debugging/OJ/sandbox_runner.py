import asyncio
import os
import re
import uuid
from typing import Tuple, List
import platform # 新增: 引入 platform
import subprocess # 新增: 引入 subprocess
from starlette.concurrency import run_in_threadpool # 新增: 引入 run_in_threadpool (從 FastAPI 或 Starlette 獲取)
from .models import ExecutionOutcome

# Docker image name (from env or default)
SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "oj-sandbox-python")

MAX_CODE_BYTES = 20000
MAX_OUTPUT_CHARS = 32000

# Forbidden patterns
FORBIDDEN = [
    r"import\s+os",
    r"import\s+sys",
    r"import\s+subprocess",
    r"import\s+socket",
    r"import\s+multiprocessing",
    r"os\.system\s*\(",
    r"sys\.modules",
    r"open\s*\(",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__",
]

def safe_check(code: str):
    """Check user code for forbidden operations."""
    for pattern in FORBIDDEN:
        if re.search(pattern, code):
            raise ValueError(f"Forbidden operation detected: {pattern}")


# 新增: 同步版本的 Docker 執行函式 (專門給 Windows 主機使用)
def _run_docker_sync_win(cmd: List[str], code: str, timeout: float) -> Tuple[str, str, int, str]:
    """
    在 Windows 主機環境下，使用同步方式執行 Docker。
    這可以繞過 asyncio.create_subprocess_exec 的 NotImplementedError。
    """
    container_name = cmd[cmd.index("--name") + 1]
    try:
        # 將 cmd 列表轉換成字串，適用於 shell=True
        cmd_str = " ".join(cmd)
        
        # 執行 subprocess.run，並設定 timeout
        proc_result = subprocess.run(
            cmd_str,
            input=code.encode('utf-8'),
            capture_output=True,
            # timeout=int(timeout)+1,
            shell=True, # 必須使用 shell=True 才能在 Windows 找到 docker CLI
            check=False 
        )

        stdout = proc_result.stdout.decode("utf-8", errors="replace")
        stderr = proc_result.stderr.decode("utf-8", errors="replace")
        returncode = proc_result.returncode
        
        # 檢查 Docker CLI 是否報告錯誤 (stderr 裡是否有明顯的 CLI 錯誤)
        if returncode != 0 and ('Error response from daemon' in stderr or 'not found' in stderr):
            return stdout, stderr, -1, "docker_cli_error"
        
        return stdout, stderr, returncode, ""

    except FileNotFoundError:
        return "", "docker executable not found (sync mode)", -1, "docker_err"
    except subprocess.TimeoutExpired:
        # 在同步模式下，TimeoutExpired 後我們需要手動 kill 容器
        # container_name = cmd[cmd.index("--name") + 1]
        try:
             # 使用同步 kill
            #  subprocess.run(["docker", "kill", container_name], capture_output=True, timeout=5)
            subprocess.run(f"docker kill {container_name}", shell=True, capture_output=True, timeout=5)
        except Exception:
             pass
        return "", "", -1, "timeout"
    except Exception as e:
        return "", f"docker run failed sync: {type(e).__name__}: {e}", -1, "docker_err"


async def _run_docker_async(code: str, timeout: float) -> Tuple[str, str, int, str]:
    """Run code inside Docker sandbox."""
    container_name = f"sandbox_{uuid.uuid4().hex[:8]}"
    check_cmd = ["docker", "image", "inspect", SANDBOX_IMAGE]

    cmd = [
        "docker", "run",
        "--name", container_name,
        "--rm",
        "--interactive",
        # 新增: 使用 --init 確保 TLE 時進程能被正確終止
        "--init",
        # 新增: 使用 --stop-timeout 讓 Docker Daemon 在 TLE 時等待並自動發送 SIGKILL
        f"--stop-timeout={int(timeout)+1}",
        "--network", "none",
        "--cpus", "1.5",
        "--memory", "256m",
        "--memory-swap", "256m",
        "--pids-limit", "64",
        "--cap-drop=ALL",
        "--security-opt", "no-new-privileges",
        SANDBOX_IMAGE,
        # 最終修復：使用 sh -c "cat | python" 確保 stdin 編碼正確
        "sh", "-c", "python -u -c \"import sys; exec(sys.stdin.read())\""
        # 注意: 如果上面的 sh -c 失敗，請替換成：
        # "python", "-u", "-c", "import sys; exec(sys.stdin.read(sys.stdin.fileno()).decode('utf-8'))"
        # "python", "-u", "-c", "import sys; exec(sys.stdin.read())",
    ]

    # 步驟 1: 環境偵測與分流 (Windows/Linux)
    if platform.system() == "Windows":
        try:
            # 讓 run_in_threadpool 執行同步函式，實現非阻塞
            thread_task = run_in_threadpool(_run_docker_sync_win, cmd, code, timeout)
            
            # 使用 asyncio.wait_for 處理超時
            return await asyncio.wait_for(thread_task, timeout=timeout + 5) # 額外給予 5 秒緩衝
            
        except asyncio.TimeoutError:
            # 如果在這裡超時，表示整個 threadpool 任務都卡住了 (例如 Docker Daemon 本身出了問題)
            print(f"Async timeout for container {container_name}. Attempting sync kill in threadpool.")
            try:
                # 執行 docker kill
                await run_in_threadpool(
                    subprocess.run, 
                    f"docker kill {container_name}", 
                    shell=True, 
                    capture_output=True, 
                    timeout=5
                )
            except Exception as e:
                # 無法殺死容器
                print(f"Failed to kill container {container_name}: {e}")
                pass
            return "", "", -1, "docker_err_thread_timeout" 
        except Exception as e:
            return "", f"Threadpool execution failed: {type(e).__name__}: {e}", -1, "docker_err"

    # 步驟 2: Linux/macOS 環境 (使用原生 asyncio)
    try:
        check_proc = await asyncio.create_subprocess_exec(
            *check_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await check_proc.wait()
        
        # 如果退出碼非 0，表示映像檔不存在
        if check_proc.returncode != 0:
            stderr_output = (await check_proc.stderr.read()).decode("utf-8", errors="replace")
            return "", f"Sandbox image '{SANDBOX_IMAGE}' not found on Docker host: {stderr_output}", -1, "docker_err_no_image"
            
    except Exception as e:
        # 如果連 docker image inspect 都失敗，可能是 docker daemon 連接問題
        return "", f"Docker service unreachable during image check: {e}", -1, "docker_err_no_image"

    # Start docker process 
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return "", "docker executable not found in Python subprocess environment", -1, "docker_err"
    except Exception as e:
        return "", f"docker run failed: {type(e).__name__}: {e}", -1, "docker_err"

    # Execute inside timeout
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=code.encode()),
            timeout=timeout
        )
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # Output truncation
        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS] + "\n...[output truncated]..."
        if len(stderr) > MAX_OUTPUT_CHARS:
            stderr = stderr[:MAX_OUTPUT_CHARS] + "\n...[stderr truncated]..."

        return stdout, stderr, proc.returncode, ""

    except asyncio.TimeoutError:
        # Kill container
        try:
            proc.kill()
            await proc.communicate()
        except:
            pass

        try:
            # 必須使用原本的 asyncio.create_subprocess_exec 殺死容器
            killer = await asyncio.create_subprocess_exec("docker", "kill", container_name)
            await killer.wait()
        except Exception as e:
            print(f"Error killing container {container_name}: {e}")
            pass

        return "", "", -1, "timeout"

    except Exception as e:
        return "", str(e), -1, "docker_err"


async def run_in_sandbox(code: str, timeout: float) -> ExecutionOutcome:
    """High-level sandbox execution wrapper."""
    # Size limit
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return ExecutionOutcome(
            status="error", stdout="", error_text="Source code too large."
        )

    stdout, stderr, returncode, extra_err = await _run_docker_async(code, timeout)
    print(returncode, extra_err)

    # Docker internal error → 判題系統中止
    # 捕獲來自兩種執行模式的 docker_err 或 docker_cli_error
    if extra_err == "docker_err" or extra_err == "docker_cli_error" or extra_err == "docker_err_no_image":
        # 將詳細錯誤訊息包含在 RuntimeError 中，以便傳遞到 judge_core
        raise RuntimeError(f"SandboxUnavailable: {stderr.strip() or stdout.strip()}")

    # Timeout
    if extra_err == "timeout"or extra_err == "docker_err_thread_timeout":
        return ExecutionOutcome(
            status="timeout", stdout="", error_text="Time Limit Exceeded"
        )

    if returncode == 137 and not stdout and not stderr:
        return ExecutionOutcome(
            status="timeout", stdout="", error_text="Time Limit Exceeded (SIGKILL)"
        )
    
    # Runtime Error
    if returncode != 0:
        return ExecutionOutcome(
            status="error",
            stdout=stdout,
            error_text=stderr.strip() or f"Exited {returncode}",
        )

    # OK
    return ExecutionOutcome(status="ok", stdout=stdout, error_text="")