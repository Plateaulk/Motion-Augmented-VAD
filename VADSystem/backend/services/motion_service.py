"""Motion Service - MotionStreamer Integration"""
import os
import sys
import json
import uuid
import subprocess
import time
import glob
import filecmp
import threading
import re
import urllib.request
import urllib.error
from typing import Optional, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MOTIONSTREAMER_PATH, MOTION_OUTPUT_DIR,
    SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR,
    SHT_MOTION_DIR, UCF_MOTION_DIR,
    MOTIONSTREAMER_PYTHON, MOTION_SERVER_URL
)

# Global task storage for async operations
_motion_tasks: Dict[str, dict] = {}
_task_lock = threading.Lock()


def find_motion_path(motion_id, directory, search_dirs):
    """Resolve a motion in the selected runs directory, or use the caller's legacy search order."""
    if not isinstance(motion_id, str) or os.path.basename(motion_id) != motion_id or motion_id in ('', '.', '..'):
        return None
    if directory:
        if not isinstance(directory, str) or not directory.startswith('runs_') or os.path.basename(directory) != directory:
            return None
        search_dirs = [os.path.join(MOTIONSTREAMER_PATH, directory)]
    for root in search_dirs:
        path = os.path.join(root, motion_id)
        if os.path.isdir(path):
            return path
    return None


def get_task(task_id: str) -> Optional[dict]:
    """Get task info by ID"""
    with _task_lock:
        return _motion_tasks.get(task_id, {}).copy() if task_id in _motion_tasks else None


def update_task(task_id: str, updates: dict):
    """Update task info"""
    with _task_lock:
        if task_id in _motion_tasks:
            _motion_tasks[task_id].update(updates)


def create_task(task_id: str, task_type: str, **kwargs) -> dict:
    """Create a new task"""
    task = {
        "task_id": task_id,
        "type": task_type,
        "status": "pending",
        "progress": 0,
        "message": "Preparing...",
        "created_at": time.time(),
        "output": "",
        **kwargs
    }
    with _task_lock:
        _motion_tasks[task_id] = task
    return task


class MotionService:
    """Service for motion generation using MotionStreamer"""
    
    def __init__(self):
        self.motionstreamer_path = MOTIONSTREAMER_PATH
        self.python_path = MOTIONSTREAMER_PYTHON
        self.output_dir = MOTION_OUTPUT_DIR
        self.sht_motion_dir = SHT_MOTION_DIR
        self.ucf_motion_dir = UCF_MOTION_DIR
        self.jobs: Dict[str, dict] = {}
        os.makedirs(self.output_dir, exist_ok=True)
    
    def get_motion_dir(self, dataset: str = 'sht') -> str:
        """Get motion directory based on dataset"""
        if dataset == 'ucf' or dataset == 'ucf-crime':
            return self.ucf_motion_dir
        else:
            return self.sht_motion_dir
    
    def _is_motion_server_ready(self) -> bool:
        """Check if the persistent motion server is running and ready."""
        try:
            req = urllib.request.Request(f"{MOTION_SERVER_URL}/health", method="GET")
            resp = urllib.request.urlopen(req, timeout=2)
            data = json.loads(resp.read())
            return data.get("status") == "ready"
        except Exception:
            return False

    def _start_motion_server(self):
        """Start the persistent motion server if not already running."""
        if self._is_motion_server_ready():
            return True
        
        print("[MotionService] Starting persistent motion server...")
        cmd = [
            self.python_path, "motion_server.py",
            "--port", "5100"
        ]
        # Start as a detached background process
        subprocess.Popen(
            cmd,
            cwd=self.motionstreamer_path,
            stdout=open(os.path.join(self.motionstreamer_path, "motion_server.log"), "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        
        # Wait for server to become ready (up to 120s for model loading)
        for i in range(120):
            time.sleep(1)
            if self._is_motion_server_ready():
                print(f"[MotionService] Motion server ready after {i+1}s")
                return True
            if i % 10 == 0 and i > 0:
                print(f"[MotionService] Still waiting for motion server... ({i}s)")
        
        print("[MotionService] Motion server failed to start within 120s")
        return False

    def generate_motion(
        self, 
        text: str, 
        motion_id: str = None,
        output_dir: str = None,
        async_mode: bool = True
    ) -> dict:
        """Generate motion from text description
        
        Uses the persistent motion server (models loaded once) for fast generation.
        Falls back to subprocess if server is unavailable.
        
        Args:
            text: Motion description
            motion_id: Custom motion ID (optional)
            output_dir: Target directory name like 'runs_sht_abnormal' (optional)
            async_mode: Run in background and return immediately (default True)
        """
        if motion_id is None:
            motion_id = str(uuid.uuid4())[:8]
        
        task_id = f"motion_{motion_id}_{int(time.time())}"
        
        # Determine output root directory
        if output_dir:
            out_root = os.path.join(self.motionstreamer_path, output_dir)
        else:
            out_root = self.output_dir
        
        output_path = os.path.join(out_root, motion_id)
        os.makedirs(output_path, exist_ok=True)
        
        # Create task
        create_task(
            task_id, 
            "motion_generate",
            motion_id=motion_id,
            text=text,
            output_path=output_path
        )
        
        # Create config file for batch processing
        config = {
            "id": motion_id,
            "text": text,
            "output_dir": output_dir or "default"
        }
        
        config_file = os.path.join(output_path, "config.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        if async_mode:
            # Run in background thread
            def run_motion_generation():
                # Try persistent motion server first; start it if not running
                server_ready = self._is_motion_server_ready()
                if not server_ready:
                    update_task(task_id, {"status": "running", "progress": 5, "message": "Starting motion server (first run)..."})
                    server_ready = self._start_motion_server()
                
                if server_ready:
                    update_task(task_id, {"status": "running", "progress": 20, "message": "Calling inference service..."})
                    server_request_done = threading.Event()

                    def _progress_while_waiting():
                        """Move progress 20 -> 85 over ~60s so the bar keeps moving during server inference."""
                        start = time.time()
                        while not server_request_done.wait(timeout=4):
                            t = get_task(task_id)
                            if not t or t.get("status") != "running":
                                break
                            elapsed = time.time() - start
                            # Ramp from 20 to 85 over ~60s, then hold
                            p = min(85, 20 + int(elapsed * 1.1))
                            if p > (t.get("progress") or 0):
                                update_task(task_id, {"progress": p, "message": "Generating motion..."})

                    try:
                        payload = json.dumps({
                            "text": text,
                            "out_root": out_root,
                            "sample_id": motion_id,
                        }).encode("utf-8")
                        
                        req = urllib.request.Request(
                            f"{MOTION_SERVER_URL}/generate",
                            data=payload,
                            headers={"Content-Type": "application/json"},
                            method="POST"
                        )
                        ticker = threading.Thread(target=_progress_while_waiting, daemon=True)
                        ticker.start()
                        try:
                            resp = urllib.request.urlopen(req, timeout=300)
                            result = json.loads(resp.read())
                        finally:
                            server_request_done.set()
                        
                        if result.get("success"):
                            update_task(task_id, {
                                "status": "completed",
                                "progress": 100,
                                "message": f"Done! ({result.get('elapsed', '?')}s)",
                                "output": json.dumps(result)
                            })
                            return
                        else:
                            error_msg = result.get("error", "Unknown error")
                            update_task(task_id, {
                                "status": "failed",
                                "progress": 0,
                                "message": f"Generation failed: {error_msg}",
                                "error": error_msg
                            })
                            return
                    except Exception as e:
                        server_request_done.set()
                        print(f"[MotionService] Motion server call failed: {e}, falling back to subprocess")
                        # Fall through to subprocess fallback
                
                # Fallback: subprocess (slow, reloads models)
                update_task(task_id, {"status": "running", "progress": 5, "message": "Loading model (slow on first run)..."})
                cmd = [
                    self.python_path, "demo_t2m_batch.py",
                    "--text", text,
                    "--out_root", out_root,
                    "--sample_id", motion_id,
                    "--resume-pth", "Causal_TAE/net_last.pth",
                    "--resume-trans", "Experiments/t2m_model/latest.pth"
                ]
                subprocess_done = threading.Event()

                def progress_ticker():
                    """Update message every 10s so UI does not look stuck."""
                    start = time.time()
                    while not subprocess_done.wait(timeout=10):
                        t = get_task(task_id)
                        if not t or t.get("status") != "running" or t.get("progress", 0) != 5:
                            break
                        elapsed = int(time.time() - start)
                        update_task(task_id, {"message": f"Loading model (slow on first run)... {elapsed}s"})

                try:
                    process = subprocess.Popen(
                        cmd,
                        cwd=self.motionstreamer_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    ticker = threading.Thread(target=progress_ticker, daemon=True)
                    ticker.start()

                    output_lines = []
                    for line in iter(process.stdout.readline, ''):
                        output_lines.append(line)
                        if "loading checkpoint" in line.lower():
                            update_task(task_id, {"progress": 20, "message": "Loading checkpoint..."})
                        elif "loading transformer" in line.lower():
                            update_task(task_id, {"progress": 30, "message": "Loading Transformer..."})
                        elif "[Demo] repeated motion" in line or "motion_272_denorm" in line:
                            update_task(task_id, {"progress": 70, "message": "Generating motion..."})
                        elif "pelvis disp" in line:
                            update_task(task_id, {"progress": 85, "message": "Saving results..."})
                        elif "[Demo] saved sample" in line:
                            update_task(task_id, {"progress": 95, "message": "Finalizing..."})

                    subprocess_done.set()
                    process.wait()
                    
                    if process.returncode == 0:
                        update_task(task_id, {
                            "status": "completed",
                            "progress": 100,
                            "message": "Done!",
                            "output": "".join(output_lines[-20:])
                        })
                    else:
                        update_task(task_id, {
                            "status": "failed",
                            "progress": 0,
                            "message": "Generation failed",
                            "error": "".join(output_lines[-10:])
                        })
                        
                except Exception as e:
                    subprocess_done.set()
                    update_task(task_id, {
                        "status": "failed",
                        "progress": 0,
                        "message": str(e),
                        "error": str(e)
                    })
            
            thread = threading.Thread(target=run_motion_generation, daemon=True)
            thread.start()
            
            return {
                "success": True,
                "task_id": task_id,
                "motion_id": motion_id,
                "message": "Motion generation started"
            }
        else:
            # Synchronous mode
            if self._is_motion_server_ready():
                try:
                    payload = json.dumps({
                        "text": text,
                        "out_root": out_root,
                        "sample_id": motion_id,
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        f"{MOTION_SERVER_URL}/generate",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    resp = urllib.request.urlopen(req, timeout=300)
                    result = json.loads(resp.read())
                    if result.get("success"):
                        return {
                            "success": True,
                            "motion_id": motion_id,
                            "output_path": output_path,
                            "files": self._get_output_files(output_path)
                        }
                    else:
                        return {"success": False, "motion_id": motion_id, "error": result.get("error", "unknown")}
                except Exception as e:
                    print(f"[MotionService] Server call failed: {e}, falling back to subprocess")
            
            # Subprocess fallback
            cmd = [
                self.python_path, "demo_t2m_batch.py",
                "--text", text,
                "--out_root", out_root,
                "--sample_id", motion_id,
                "--resume-pth", "Causal_TAE/net_last.pth",
                "--resume-trans", "Experiments/t2m_model/latest.pth"
            ]
            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.motionstreamer_path,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    return {
                        "success": True,
                        "motion_id": motion_id,
                        "output_path": output_path,
                        "files": self._get_output_files(output_path)
                    }
                else:
                    return {"success": False, "motion_id": motion_id, "error": result.stderr}
                    
            except subprocess.TimeoutExpired:
                return {"success": False, "motion_id": motion_id, "error": "Motion generation timed out"}
            except Exception as e:
                return {"success": False, "motion_id": motion_id, "error": str(e)}
    
    def _get_render_dir_name(
        self, 
        background: str, 
        yaw_deg: float, 
        height: float, 
        distance: float, 
        dataset: str
    ) -> str:
        """Generate unique render directory name based on parameters"""
        # Extract background name without extension
        bg_name = os.path.splitext(background)[0] if background else "default"
        # Clean up special characters
        bg_name = bg_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        # Format: render_{dataset}_{bg}_yaw{yaw}_h{height}_d{distance}
        return f"render_{dataset}_{bg_name}_yaw{int(yaw_deg)}_h{height:.1f}_d{distance:.1f}"
    
    def render_mask_video(
        self,
        motion_id: str,
        background: str = None,
        yaw_deg: float = -60,
        height: float = 1.5,
        distance: float = 3.0,
        dataset: str = 'sht',
        render_name: str = None,
        output_dir: str = None,
        video_width: int = 856,
        video_height: int = 480,
        source_directory: str = None,
    ) -> dict:
        """Render mask video from motion
        
        Args:
            motion_id: ID of the motion to render
            background: Background image filename
            yaw_deg: Camera yaw angle in degrees (-180 to 180)
            height: Camera height in meters (0 to 3)
            distance: Camera distance in meters (1 to 10)
            dataset: Dataset type ('sht' or 'ucf')
            render_name: Custom name for the render output directory
            output_dir: Target directory name (e.g. 'runs_sht_abnormal'). If set, render into that directory's copy of the motion.
            video_width: Output video width (256-1920)
            video_height: Output video height (256-1080)
        """
        # Validate resolution
        video_width = max(256, min(1920, video_width))
        video_height = max(256, min(1080, video_height))
        
        search_dirs = [self.get_motion_dir(dataset), self.output_dir]
        if not source_directory:
            search_dirs.extend(glob.glob(os.path.join(self.motionstreamer_path, "runs_*")))
        source_motion_path = find_motion_path(motion_id, source_directory, search_dirs)
        
        if not source_motion_path:
            return {"success": False, "error": f"Motion not found: {motion_id}"}
        
        # Determine render target path
        if output_dir:
            # Render into specified output directory
            target_dir = os.path.join(self.motionstreamer_path, output_dir)
            os.makedirs(target_dir, exist_ok=True)
            motion_path = os.path.join(target_dir, motion_id)
            
            # If source and target are different, copy motion files
            if os.path.realpath(source_motion_path) != os.path.realpath(motion_path):
                existing = os.path.join(motion_path, "motion_272_denorm.npy")
                source = os.path.join(source_motion_path, "motion_272_denorm.npy")
                if not os.path.isfile(source):
                    return {"success": False, "error": "Selected motion file not found"}
                if os.path.isfile(existing) and not filecmp.cmp(source, existing, shallow=False):
                    return {"success": False, "error": "The output directory already contains a different motion with this ID"}
                os.makedirs(motion_path, exist_ok=True)
                import shutil
                for fname in ["motion_272_norm.npy", "motion_272_denorm.npy", 
                              "joints_xyz.npy", "pelvis_traj.npy", "config.json"]:
                    src = os.path.join(source_motion_path, fname)
                    dst = os.path.join(motion_path, fname)
                    if os.path.exists(src) and not os.path.exists(dst):
                        shutil.copy2(src, dst)
        else:
            motion_path = source_motion_path
        
        if not os.path.exists(motion_path):
            return {"success": False, "error": f"Motion not found: {motion_id}"}
        
        # Check for required motion files
        motion_file = os.path.join(motion_path, "motion_272_denorm.npy")
        if not os.path.exists(motion_file):
            return {"success": False, "error": "Motion file not found. Please generate motion first."}
        
        # Get background image path
        if background:
            if dataset == 'sht':
                bg_path = os.path.join(SHT_BACKGROUND_DIR, background)
            else:
                bg_path = os.path.join(UCF_BACKGROUND_DIR, background)
            
            if not os.path.exists(bg_path):
                return {"success": False, "error": f"Background image not found: {background}"}
        else:
            # Use default background
            if dataset == 'sht':
                bg_path = os.path.join(SHT_BACKGROUND_DIR, "01.jpg")
                background = "01.jpg"
            else:
                bg_path = os.path.join(UCF_BACKGROUND_DIR, "003.jpg")
                background = "003.jpg"
        
        # Generate unique render directory name
        if render_name:
            # Use custom render name
            render_dir_name = f"render_{render_name}"
        else:
            render_dir_name = self._get_render_dir_name(background, yaw_deg, height, distance, dataset)
        render_dir = os.path.join(motion_path, render_dir_name)
        
        # Calculate camera position based on height and distance
        # Height: y-component, Distance: z-component
        cam_eye_y = height * 3  # Scale factor: 1.0 -> 3
        cam_eye_z = distance * 5  # Scale factor: 1.0 -> 5
        cam_eye = f"0,{cam_eye_y:.1f},{cam_eye_z:.1f}"
        
        # Save render config for this specific render
        render_config = {
            "motion_id": motion_id,
            "background": background,
            "yaw_deg": yaw_deg,
            "height": height,
            "distance": distance,
            "cam_eye": cam_eye,
            "dataset": dataset,
            "render_dir": render_dir_name,
            "video_width": video_width,
            "video_height": video_height,
            "created_at": time.time()
        }
        
        # Find motion npy file
        motion_npy = os.path.join(motion_path, "motion_272_denorm.npy")
        if not os.path.exists(motion_npy):
            return {"success": False, "error": "Motion npy file not found"}
        
        # Run mask rendering
        cmd = [
            self.python_path, "render_motionstreamer_to_mask_video.py",
            "--motion_npy", motion_npy,
            "--background", bg_path,
            "--yaw_deg", str(yaw_deg),
            "--cam_eye", cam_eye,
            "--out_dir", render_dir,
            "--width", str(video_width),
            "--height", str(video_height),
            "--fit_screen"
        ]
        
        # Create task for tracking
        task_id = f"render_{motion_id}_{int(time.time())}"
        create_task(
            task_id,
            "render",
            motion_id=motion_id,
            render_dir=render_dir,
            render_dir_name=render_dir_name,
            background=background
        )
        
        # Run in background thread
        def run_render():
            update_task(task_id, {"status": "running", "progress": 5, "message": "Initializing render..."})
            try:
                process = subprocess.Popen(
                    cmd,
                    cwd=self.motionstreamer_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                output_lines = []
                for line in iter(process.stdout.readline, ''):
                    output_lines.append(line)
                    # Parse tqdm progress: "Render:  50%|█████     | 50/100 [00:05<00:05]"
                    tqdm_match = re.search(r'(\d+)%\|', line)
                    if tqdm_match:
                        progress = int(tqdm_match.group(1))
                        # Scale to 10-90 range
                        scaled_progress = 10 + int(progress * 0.8)
                        update_task(task_id, {"progress": scaled_progress, "message": f"Rendering {progress}%..."})
                    elif "device=" in line:
                        update_task(task_id, {"progress": 10, "message": "Loading SMPL model..."})
                    elif "using SMPL" in line:
                        update_task(task_id, {"progress": 15, "message": "Preparing render..."})
                    elif "[Done]" in line:
                        update_task(task_id, {"progress": 95, "message": "Exporting video..."})
                
                process.wait()
                
                if process.returncode == 0:
                    # Save render config
                    config_file = os.path.join(render_dir, "render_config.json")
                    os.makedirs(render_dir, exist_ok=True)
                    with open(config_file, 'w') as f:
                        json.dump(render_config, f, indent=2)
                    
                    update_task(task_id, {
                        "status": "completed",
                        "progress": 100,
                        "message": "Done!",
                        "result": {
                            "motion_id": motion_id,
                            "render_id": render_dir_name,
                            "render_dir": render_dir,
                            "background": background,
                            "mask_video": os.path.join(render_dir, "mask.mp4"),
                            "composite_video": os.path.join(render_dir, "composite.mp4")
                        }
                    })
                else:
                    update_task(task_id, {
                        "status": "failed",
                        "progress": 0,
                        "message": "Render failed",
                        "error": "".join(output_lines[-10:])
                    })
                    
            except Exception as e:
                update_task(task_id, {
                    "status": "failed",
                    "progress": 0,
                    "message": str(e),
                    "error": str(e)
                })
        
        thread = threading.Thread(target=run_render, daemon=True)
        thread.start()
        
        return {
            "success": True,
            "task_id": task_id,
            "motion_id": motion_id,
            "render_id": render_dir_name,
            "message": "Rendering started"
        }
    
    def get_task_progress(self, task_id: str) -> dict:
        """Get progress of a motion/render task"""
        task = get_task(task_id)
        if not task:
            return {"error": "Task not found", "status": "unknown"}
        return {
            "task_id": task_id,
            "type": task.get("type"),
            "status": task.get("status", "unknown"),
            "progress": task.get("progress", 0),
            "message": task.get("message", ""),
            "error": task.get("error"),
            "result": task.get("result")
        }
    
    def get_video_path(self, motion_id: str, video_type: str = 'composite', dataset: str = None,
                       render_id: str = None, directory: str = None) -> Optional[str]:
        """Get path to rendered video file"""
        motion_path = find_motion_path(motion_id, directory, [self.sht_motion_dir, self.ucf_motion_dir, self.output_dir])
        
        if not motion_path:
            return None
        
        # If specific render_id is provided, use it
        if render_id:
            render_dir = os.path.join(motion_path, render_id)
            if not os.path.exists(render_dir):
                return None
        else:
            # Find all render directories (both old and new formats)
            render_dirs = glob.glob(os.path.join(motion_path, "render_*"))
            if not render_dirs:
                return None
            
            # Sort by modification time, use the most recent
            render_dirs = sorted(render_dirs, key=lambda d: os.path.getmtime(d), reverse=True)
            render_dir = render_dirs[0]
        
        if video_type == 'composite':
            video_path = os.path.join(render_dir, "composite.mp4")
        elif video_type == 'mask':
            video_path = os.path.join(render_dir, "mask.mp4")
        else:
            return None
        
        if os.path.exists(video_path):
            return video_path
        return None
    
    def list_renders(self, motion_id: str, dataset: str = 'sht') -> List[dict]:
        """List all renders for a specific motion"""
        # Find motion path
        motion_dir = self.get_motion_dir(dataset)
        motion_path = os.path.join(motion_dir, motion_id)
        
        if not os.path.exists(motion_path):
            motion_path = os.path.join(self.output_dir, motion_id)
        
        return self.list_renders_from_path(motion_path, motion_id)
    
    def list_renders_from_path(self, motion_path: str, motion_id: str = None) -> List[dict]:
        """List all renders from a specific motion path"""
        renders = []
        
        if not os.path.exists(motion_path):
            return renders
        
        if motion_id is None:
            motion_id = os.path.basename(motion_path)
        
        # Find all render directories
        render_dirs = glob.glob(os.path.join(motion_path, "render_*"))
        
        for render_dir in render_dirs:
            render_id = os.path.basename(render_dir)
            composite_video = os.path.join(render_dir, "composite.mp4")
            mask_video = os.path.join(render_dir, "mask.mp4")
            
            # Try to load render config
            config_file = os.path.join(render_dir, "render_config.json")
            config = {}
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                except:
                    pass
            
            # Parse render_id for old format (render_yawXXX)
            background = config.get("background", "")
            yaw_deg = config.get("yaw_deg", 0)
            render_dataset = config.get("dataset", "")
            
            if not background and "yaw" in render_id:
                # Old format: render_yawm60p0 or render_yaw90
                parts = render_id.split("yaw")
                if len(parts) > 1:
                    yaw_str = parts[1].replace("m", "-").replace("p", ".")
                    try:
                        yaw_deg = float(yaw_str)
                    except:
                        pass
            
            renders.append({
                "render_id": render_id,
                "motion_id": motion_id,
                "motion_path": motion_path,
                "background": background,
                "yaw_deg": yaw_deg,
                "height": config.get("height", 1.5),
                "distance": config.get("distance", 3.0),
                "dataset": render_dataset,
                "has_composite": os.path.exists(composite_video),
                "has_mask": os.path.exists(mask_video),
                "composite_video": composite_video if os.path.exists(composite_video) else None,
                "mask_video": mask_video if os.path.exists(mask_video) else None,
                "created_at": config.get("created_at", os.path.getctime(render_dir))
            })
        
        return sorted(renders, key=lambda x: x["created_at"], reverse=True)
    
    def _get_output_files(self, output_path: str) -> List[str]:
        """Get list of output files"""
        files = []
        if os.path.exists(output_path):
            for f in os.listdir(output_path):
                if f.endswith(('.npy', '.mp4', '.json')):
                    files.append(f)
        return files
    
    def list_motions(self, dataset: str = 'sht') -> List[dict]:
        """List all generated motions with rendered video info for a specific dataset"""
        motion_dir = self.get_motion_dir(dataset)
        return self.list_motions_from_dir(motion_dir, dataset)
    
    def list_motions_from_dir(self, motion_dir: str, directory_name: str = '') -> List[dict]:
        """List all generated motions from a specific directory"""
        motions = []
        
        if not os.path.exists(motion_dir):
            return motions
        
        for motion_id in os.listdir(motion_dir):
            motion_path = os.path.join(motion_dir, motion_id)
            if os.path.isdir(motion_path):
                # Check for motion file to verify it's a valid motion directory
                motion_file = os.path.join(motion_path, "motion_272_denorm.npy")
                if not os.path.exists(motion_file):
                    continue
                
                # Try to load config if exists
                config_file = os.path.join(motion_path, "config.json")
                config = {}
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r') as f:
                            config = json.load(f)
                    except:
                        pass
                
                # Parse motion name for text description
                # Format: SHT_fall_01 or 900001
                text = config.get("text", "")
                if not text:
                    if motion_id.startswith("SHT_"):
                        # Parse SHT format: SHT_action_num
                        parts = motion_id.split("_")
                        if len(parts) >= 2:
                            text = parts[1].replace("_", " ")
                    elif motion_id.isdigit():
                        text = f"Anomaly {motion_id}"
                    else:
                        text = motion_id
                
                # Get all renders for this motion
                renders = self.list_renders_from_path(motion_path)
                
                # Get the latest render for backward compatibility
                composite_video = None
                mask_video = None
                background = config.get("background", "")
                
                if renders:
                    latest_render = renders[0]  # Already sorted by created_at desc
                    composite_video = latest_render.get("composite_video")
                    mask_video = latest_render.get("mask_video")
                    if not background:
                        background = latest_render.get("background", "")
                
                motions.append({
                    "motion_id": motion_id,
                    "text": text,
                    "background": background,
                    "directory": directory_name,
                    "motion_path": motion_path,
                    "has_mask": mask_video is not None,
                    "composite_video": composite_video,
                    "mask_video": mask_video,
                    "renders": renders,
                    "render_count": len(renders),
                    "created_at": os.path.getctime(motion_path)
                })
        
        return sorted(motions, key=lambda x: x["created_at"], reverse=True)
    
    def get_status(self, motion_id: str) -> dict:
        """Get status of a motion generation job"""
        if motion_id in self.jobs:
            return self.jobs[motion_id]
        
        # Check if motion exists on disk
        motion_path = os.path.join(self.output_dir, motion_id)
        if os.path.exists(motion_path):
            files = self._get_output_files(motion_path)
            return {
                "status": "completed" if files else "unknown",
                "motion_id": motion_id,
                "output_path": motion_path,
                "files": files
            }
        
        return {"status": "not_found", "motion_id": motion_id}
    
    def _find_motion_path(self, motion_id: str) -> Optional[str]:
        """Find motion directory in output_dir or any runs_* directory."""
        candidate = os.path.join(self.output_dir, motion_id)
        if os.path.exists(candidate) and os.path.isdir(candidate):
            return candidate
        for item in os.listdir(self.motionstreamer_path):
            if item.startswith("runs_"):
                candidate = os.path.join(self.motionstreamer_path, item, motion_id)
                if os.path.exists(candidate) and os.path.isdir(candidate):
                    return candidate
        return None

    def delete_motion(self, motion_id: str) -> dict:
        """Move motion folder to recycle bin (trash) so it appears in Trash tab."""
        motion_path = self._find_motion_path(motion_id)
        if not motion_path:
            return {"success": False, "error": f"Motion not found: {motion_id}"}
        try:
            from services.trash_service import trash_folder
            entry = trash_folder(motion_path)
            if motion_id in self.jobs:
                del self.jobs[motion_id]
            if entry:
                return {"success": True, "motion_id": motion_id, "trash_id": entry["id"]}
            return {"success": False, "error": "Failed to move to trash"}
        except Exception as e:
            return {"success": False, "error": str(e)}
