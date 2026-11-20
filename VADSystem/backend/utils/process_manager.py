"""Process Manager for external services (ComfyUI, training, etc.)"""
import subprocess
import os
import signal
import time
import threading
from typing import Optional, Dict, Callable
import sys

class ProcessManager:
    """Manages external processes with monitoring and cleanup"""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.log_threads: Dict[str, threading.Thread] = {}
        self.running = True
    
    def start_process(
        self, 
        name: str, 
        cmd: list, 
        cwd: str = None,
        env: dict = None,
        log_callback: Callable[[str, str], None] = None
    ) -> bool:
        """Start a process and optionally monitor its output"""
        if name in self.processes and self.processes[name].poll() is None:
            return False  # Process already running
        
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        
        try:
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )
            self.processes[name] = process
            
            if log_callback:
                def monitor_output():
                    for line in process.stdout:
                        if not self.running:
                            break
                        log_callback(name, line.rstrip())
                
                thread = threading.Thread(target=monitor_output, daemon=True)
                thread.start()
                self.log_threads[name] = thread
            
            return True
        except Exception as e:
            print(f"Failed to start process {name}: {e}")
            return False
    
    def stop_process(self, name: str, timeout: int = 10) -> bool:
        """Stop a running process"""
        if name not in self.processes:
            return False
        
        process = self.processes[name]
        if process.poll() is not None:
            return True  # Already stopped
        
        try:
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            
            del self.processes[name]
            if name in self.log_threads:
                del self.log_threads[name]
            return True
        except Exception as e:
            print(f"Failed to stop process {name}: {e}")
            return False
    
    def is_running(self, name: str) -> bool:
        """Check if a process is running"""
        if name not in self.processes:
            return False
        return self.processes[name].poll() is None
    
    def get_status(self, name: str) -> dict:
        """Get process status"""
        if name not in self.processes:
            return {"status": "not_started", "pid": None}
        
        process = self.processes[name]
        if process.poll() is None:
            return {"status": "running", "pid": process.pid}
        else:
            return {"status": "stopped", "pid": None, "returncode": process.returncode}
    
    def cleanup(self):
        """Stop all processes"""
        self.running = False
        for name in list(self.processes.keys()):
            self.stop_process(name)


class ComfyUIManager:
    """Specialized manager for ComfyUI process"""
    
    def __init__(self, comfyui_path: str, host: str = "127.0.0.1", port: int = 8188, python_path: str = None):
        self.comfyui_path = comfyui_path
        self.host = host
        self.port = port
        self.python_path = python_path or sys.executable
        self.process_manager = ProcessManager()
        self.logs = []
        self.max_logs = 1000
    
    def _log_callback(self, name: str, line: str):
        self.logs.append(line)
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
    
    def start(self) -> bool:
        """Start ComfyUI server"""
        cmd = [
            self.python_path, "main.py",
            "--listen", self.host,
            "--port", str(self.port)
        ]
        return self.process_manager.start_process(
            "comfyui", cmd, 
            cwd=self.comfyui_path,
            log_callback=self._log_callback
        )
    
    def stop(self) -> bool:
        """Stop ComfyUI server - handles both managed and external processes"""
        # First try managed process
        if self.process_manager.stop_process("comfyui"):
            return True
        
        # If not managed, try multiple methods to find and kill
        killed = False
        
        try:
            # Method 1: Find process by port using /proc/net/tcp
            pids = self._find_pids_by_port(self.port)
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed = True
                except (ProcessLookupError, PermissionError):
                    pass
            
            if killed:
                time.sleep(1)
                if not self.is_running():
                    return True
            
            # Method 2: Kill by process name using pkill
            result = subprocess.run(
                ["pkill", "-f", "main.py.*--port.*8188"],
                capture_output=True
            )
            if result.returncode == 0:
                time.sleep(1)
                if not self.is_running():
                    return True
            
            # Method 3: More general pkill for ComfyUI
            result = subprocess.run(
                ["pkill", "-f", "ComfyUI"],
                capture_output=True
            )
            time.sleep(1)
            
            # Final check
            return not self.is_running()
            
        except Exception as e:
            print(f"Error stopping ComfyUI: {e}")
            return not self.is_running()
    
    def _find_pids_by_port(self, port: int) -> list:
        """Find PIDs using a specific port by reading /proc/net/tcp"""
        pids = []
        port_hex = format(port, '04X')
        
        try:
            # Read /proc/net/tcp and /proc/net/tcp6
            for tcp_file in ['/proc/net/tcp', '/proc/net/tcp6']:
                try:
                    with open(tcp_file, 'r') as f:
                        lines = f.readlines()[1:]  # Skip header
                        for line in lines:
                            parts = line.split()
                            if len(parts) >= 10:
                                local_addr = parts[1]
                                local_port = local_addr.split(':')[1]
                                if local_port == port_hex:
                                    inode = parts[9]
                                    # Find process with this inode
                                    pid = self._find_pid_by_inode(inode)
                                    if pid and pid not in pids:
                                        pids.append(pid)
                except FileNotFoundError:
                    pass
        except Exception as e:
            print(f"Error finding PIDs by port: {e}")
        
        return pids
    
    def _find_pid_by_inode(self, inode: str) -> Optional[int]:
        """Find PID that owns a socket inode"""
        try:
            for pid_dir in os.listdir('/proc'):
                if not pid_dir.isdigit():
                    continue
                
                fd_dir = f'/proc/{pid_dir}/fd'
                try:
                    for fd in os.listdir(fd_dir):
                        try:
                            link = os.readlink(f'{fd_dir}/{fd}')
                            if f'socket:[{inode}]' in link:
                                return int(pid_dir)
                        except (FileNotFoundError, PermissionError):
                            pass
                except (FileNotFoundError, PermissionError):
                    pass
        except Exception:
            pass
        return None
    
    def is_running(self) -> bool:
        """Check if ComfyUI is running (by checking the port)"""
        import urllib.request
        import urllib.error
        
        try:
            url = f"http://{self.host}:{self.port}/system_stats"
            urllib.request.urlopen(url, timeout=2)
            return True
        except:
            return False
    
    def get_logs(self, n: int = 50) -> list:
        """Get recent logs"""
        return self.logs[-n:]
    
    def wait_ready(self, timeout: int = 60) -> bool:
        """Wait for ComfyUI to be ready"""
        import urllib.request
        import urllib.error
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                url = f"http://{self.host}:{self.port}/system_stats"
                urllib.request.urlopen(url, timeout=2)
                return True
            except (urllib.error.URLError, ConnectionRefusedError):
                time.sleep(1)
        return False


class TrainingManager:
    """Manages training processes"""
    
    def __init__(self, prodisc_path: str, python_path: str = None):
        self.prodisc_path = prodisc_path
        self.python_path = python_path or sys.executable
        self.process_manager = ProcessManager()
        self.current_job: Optional[str] = None
        self.logs = []
        self.metrics = []
        self.max_logs = 5000
        self.total_iters = 600  # Total iterations for current task
        self._log_file = None  # Persistent log file handle
        self._log_file_path = None
    
    def _log_callback(self, name: str, line: str):
        self.logs.append(line)
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
        
        # Also write to disk log file
        if self._log_file:
            try:
                self._log_file.write(line + '\n')
                self._log_file.flush()
            except Exception:
                pass
        
        # Parse AUC from log line
        if "Area Under the Curve is" in line:
            try:
                parts = line.split("Area Under the Curve is")
                auc = float(parts[1].strip())
                iter_part = parts[0].split("Iteration:")
                if len(iter_part) > 1:
                    iteration = int(iter_part[1].strip())
                    self.metrics.append({"iteration": iteration, "auc": auc})
            except:
                pass
    
    def start_training(
        self,
        job_id: str,
        dataset: str,
        seed: int,
        max_iters: int,
        k: int = 5,
        synthetic_samples: str = None,
        synthetic_ratio: Optional[float] = None,
        model_name: str = None,
        sample_size: int = 30,
        lr: float = 0.0005,
        batch_size: int = 1,
        snapshot: int = 1,
        plot: int = 0
    ) -> bool:
        """Start a training job"""
        from config import DATASET_PATH, CKPT_PATH
        # If old job exists but process is dead, auto cleanup
        if self.current_job:
            if self.process_manager.is_running(self.current_job):
                return False  # Still running, reject new task
            # Process ended, cleanup old state
            self.current_job = None
        
        self.logs = []
        self.metrics = []
        self.current_job = job_id
        self.total_iters = max_iters
        
        # Close previous log file
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None
        
        run_id = f"{time.strftime('%Y%m%d%H%M%S')}_{job_id}"
        log_dir = os.path.join(self.prodisc_path, "logs", model_name or "default_model")
        os.makedirs(log_dir, exist_ok=True)
        self._log_file_path = os.path.join(log_dir, run_id + ".log")
        try:
            self._log_file = open(self._log_file_path, 'x', encoding='utf-8')
        except OSError as error:
            print(f"Could not create training log: {error}")
            self._log_file = None

        cmd = [
            self.python_path, "main.py",
            "--dataset_name", dataset,
            "--run_id", run_id,
            "--seed", "1",
            "--dataset_path", DATASET_PATH,
            "--ckpt_path", CKPT_PATH,
            "--max_iters", str(max_iters),
            "--k", str(k),
            "--sample_size", str(sample_size),
            "--lr", str(lr),
            "--batch_size", str(batch_size),
            "--snapshot", str(snapshot),
            "--plot", str(plot),
        ]
        
        if synthetic_ratio is not None:
            cmd.extend(["--synthetic_ratio", str(synthetic_ratio)])

        if synthetic_samples:
            cmd.extend(["--synthetic_samples", synthetic_samples])
        
        if model_name:
            cmd.extend(["--model_name", model_name])
        
        return self.process_manager.start_process(
            job_id, cmd,
            cwd=self.prodisc_path,
            log_callback=self._log_callback
        )
    
    def stop_training(self) -> bool:
        """Stop current training job"""
        if not self.current_job:
            return False
        
        result = self.process_manager.stop_process(self.current_job)
        self.current_job = None
        
        # Close log file
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None
        
        return result
    
    def is_training(self) -> bool:
        """Check if training is in progress"""
        if not self.current_job:
            return False
        return self.process_manager.is_running(self.current_job)
    
    def get_status(self) -> dict:
        """Get training status"""
        if not self.current_job:
            return {"status": "idle", "job_id": None}
        
        status = self.process_manager.get_status(self.current_job)
        status["job_id"] = self.current_job
        status["metrics"] = self.metrics[-10:] if self.metrics else []
        status["best_auc"] = max([m["auc"] for m in self.metrics]) if self.metrics else None
        return status
    
    def get_logs(self, n: int = 100) -> list:
        """Get recent logs"""
        return self.logs[-n:]


# Global instances
_process_manager = None
_comfyui_manager = None
_training_manager = None

def get_process_manager() -> ProcessManager:
    global _process_manager
    if _process_manager is None:
        _process_manager = ProcessManager()
    return _process_manager

def get_comfyui_manager() -> ComfyUIManager:
    global _comfyui_manager
    if _comfyui_manager is None:
        from config import COMFYUI_PATH, COMFYUI_HOST, COMFYUI_PORT, COMFYUI_PYTHON
        _comfyui_manager = ComfyUIManager(COMFYUI_PATH, COMFYUI_HOST, COMFYUI_PORT, COMFYUI_PYTHON)
    return _comfyui_manager

def get_training_manager() -> TrainingManager:
    global _training_manager
    if _training_manager is None:
        from config import PRODISC_VAD_PATH, PRODISC_PYTHON
        _training_manager = TrainingManager(PRODISC_VAD_PATH, PRODISC_PYTHON)
    return _training_manager
