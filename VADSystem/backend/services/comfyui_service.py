"""ComfyUI Service - Video Generation"""
import hashlib
import os
import json
import uuid
import time
import urllib.request
import urllib.error
import websocket
import tempfile
import threading
from typing import Optional, Dict, List, Any

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    WORKFLOW_DIR, COMFYUI_PATH, COMFYUI_HOST, COMFYUI_PORT, COMFYUI_API_URL,
    SHT_BACKGROUND_DIR, UCF_BACKGROUND_DIR, OUTPUT_DIR, MOTION_OUTPUT_DIR,
    SHT_MOTION_DIR, UCF_MOTION_DIR
)
from utils.process_manager import get_comfyui_manager
from services.motion_service import find_motion_path


class ProgressTracker:
    """WebSocket-based real-time progress tracker for ComfyUI (≥ 0.5).
    
    CRITICAL: the same client_id MUST be used for both the WebSocket
    connection and the prompt submission, otherwise ComfyUI will not
    route execution events to this connection.
    
    ComfyUI 0.5+ sends `progress_state` (per-node state map) instead of
    the legacy `progress` message. The tracker handles both formats.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, host=None, port=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(host or COMFYUI_HOST, port or COMFYUI_PORT)
        return cls._instance
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.progress = {}
        self._ws = None
        self._thread = None
        self._running = False
        self._connected = False
        self._connect_event = threading.Event()
        self._client_id = str(uuid.uuid4())
        self._current_prompt_id = None
    
    @property
    def client_id(self):
        return self._client_id
    
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def wait_connected(self, timeout=10):
        """Block until the WebSocket is connected (or timeout)."""
        if self._connected:
            return True
        return self._connect_event.wait(timeout)
    
    def stop(self):
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
    
    def _run(self):
        while self._running:
            self._connect_event.clear()
            try:
                ws_url = f"ws://{self.host}:{self.port}/ws?clientId={self._client_id}"
                self._ws = websocket.WebSocketApp(
                    ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self._ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception:
                pass
            self._connected = False
            if self._running:
                time.sleep(2)
    
    def _on_open(self, ws):
        self._connected = True
        self._connect_event.set()
    
    def _init_progress(self, prompt_id):
        self.progress[prompt_id] = {
            'status': 'running',
            'nodes_finished': 0,
            'nodes_total': 0,
            'sampler_value': 0,
            'sampler_max': 0,
            'sampler_end_time': None,
            'start_time': time.time(),
            'message': 'Starting...',
        }
    
    # ---- message handlers ----
    
    def _on_message(self, ws, message):
        try:
            if isinstance(message, bytes):
                return
            data = json.loads(message)
            msg_type = data.get('type')
            msg_data = data.get('data', {})
            
            if msg_type == 'execution_start':
                self._handle_execution_start(msg_data)
            elif msg_type == 'progress_state':
                self._handle_progress_state(msg_data)
            elif msg_type == 'progress':
                self._handle_progress_legacy(msg_data)
            elif msg_type == 'executing':
                self._handle_executing(msg_data)
            elif msg_type == 'execution_error':
                self._handle_error(msg_data)
        except Exception:
            pass
    
    def _handle_execution_start(self, d):
        prompt_id = d.get('prompt_id')
        if prompt_id:
            self._current_prompt_id = prompt_id
            self._init_progress(prompt_id)
    
    def _handle_progress_state(self, d):
        """ComfyUI ≥ 0.5 — per-node state with value/max."""
        prompt_id = d.get('prompt_id') or self._current_prompt_id
        if not prompt_id:
            return
        if prompt_id not in self.progress:
            self._init_progress(prompt_id)
        p = self.progress[prompt_id]
        
        nodes = d.get('nodes', {})
        finished = 0
        total = len(nodes)
        best_sampler_val = p['sampler_value']
        best_sampler_max = p['sampler_max']
        running_msg = ''
        
        for nid, info in nodes.items():
            state = info.get('state', '')
            val = float(info.get('value', 0))
            mx = float(info.get('max', 1))
            
            if state == 'finished':
                finished += 1
            
            if mx > 1:
                best_sampler_val = max(best_sampler_val, val)
                best_sampler_max = max(best_sampler_max, mx)
                if state == 'running':
                    pct = int(val / mx * 100) if mx > 0 else 0
                    running_msg = f'Sampling: {int(val)}/{int(mx)} ({pct}%)'
        
        p['nodes_finished'] = finished
        p['nodes_total'] = total
        p['sampler_value'] = best_sampler_val
        p['sampler_max'] = best_sampler_max
        
        if best_sampler_max > 1 and best_sampler_val >= best_sampler_max and p['sampler_end_time'] is None:
            p['sampler_end_time'] = time.time()
        
        if running_msg:
            p['message'] = running_msg
        elif best_sampler_max > 1 and best_sampler_val >= best_sampler_max:
            p['message'] = 'Post-processing...'
        elif total > 0:
            p['message'] = f'Processing ({finished}/{total} nodes)...'
    
    def _handle_progress_legacy(self, d):
        """Legacy `progress` message (ComfyUI < 0.5)."""
        prompt_id = d.get('prompt_id') or self._current_prompt_id
        if not prompt_id:
            return
        if prompt_id not in self.progress:
            self._init_progress(prompt_id)
        p = self.progress[prompt_id]
        val = d.get('value', 0)
        mx = d.get('max', 1)
        p['sampler_value'] = max(p['sampler_value'], val)
        p['sampler_max'] = max(p['sampler_max'], mx)
        pct = int(val / mx * 100) if mx > 0 else 0
        p['message'] = f'Sampling: {val}/{mx} ({pct}%)'
        if val >= mx and mx > 1 and p['sampler_end_time'] is None:
            p['sampler_end_time'] = time.time()
    
    def _handle_executing(self, d):
        prompt_id = d.get('prompt_id')
        node_id = d.get('node')
        if prompt_id:
            self._current_prompt_id = prompt_id
            if prompt_id not in self.progress:
                self._init_progress(prompt_id)
            if node_id is None:
                self.progress[prompt_id]['status'] = 'done'
                self.progress[prompt_id]['message'] = 'Done'
    
    def _handle_error(self, d):
        prompt_id = d.get('prompt_id')
        if prompt_id:
            if prompt_id not in self.progress:
                self._init_progress(prompt_id)
            p = self.progress[prompt_id]
            p['status'] = 'error'
            exc_msg = d.get('exception_message', 'Unknown error')
            node_type = d.get('node_type', '')
            p['message'] = f'{node_type}: {exc_msg}' if node_type else exc_msg
    
    def _on_error(self, ws, error):
        self._connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        self._connected = False
    
    def get_progress(self, prompt_id):
        return self.progress.get(prompt_id)
    
    def cleanup(self, prompt_id):
        self.progress.pop(prompt_id, None)


class ComfyUIService:
    """Service for interacting with ComfyUI"""

    jobs: Dict[str, dict] = {}
    
    def __init__(self):
        self.api_url = COMFYUI_API_URL
        self.host = COMFYUI_HOST
        self.port = COMFYUI_PORT
        self.manager = get_comfyui_manager()
    
    def _ensure_tracker(self) -> ProgressTracker:
        """Start WebSocket tracker, wait for it to connect, and return it."""
        tracker = ProgressTracker.get_instance(self.host, self.port)
        tracker.start()
        tracker.wait_connected(timeout=8)
        return tracker
    
    def get_server_status(self) -> dict:
        """Check if ComfyUI server is running and responsive"""
        try:
            url = f"{self.api_url}/system_stats"
            response = urllib.request.urlopen(url, timeout=5)
            data = json.loads(response.read())
            return {
                "status": "running",
                "system_stats": data
            }
        except (urllib.error.URLError, ConnectionRefusedError):
            if self.manager.is_running():
                return {"status": "starting", "message": "ComfyUI is starting..."}
            return {"status": "stopped", "message": "ComfyUI is not running"}
    
    def start_server(self) -> dict:
        """Start ComfyUI server"""
        if self.get_server_status()["status"] == "running":
            return {"success": True, "message": "ComfyUI is already running"}
        
        if self.manager.start():
            # Wait for server to be ready
            if self.manager.wait_ready(timeout=120):
                return {"success": True, "message": "ComfyUI started successfully"}
            else:
                return {"success": False, "message": "ComfyUI started but not responding"}
        return {"success": False, "message": "Failed to start ComfyUI"}
    
    def stop_server(self) -> dict:
        """Stop ComfyUI server"""
        if self.manager.stop():
            return {"success": True, "message": "ComfyUI stopped"}
        return {"success": False, "message": "Failed to stop ComfyUI"}
    
    def get_backgrounds(self, dataset: str = 'sht', folder: str = '', search: str = '') -> List[dict]:
        """Get list of background images with optional folder filter and search"""
        from config import SYSTEM_BACKGROUND_DIR
        
        if dataset == 'sht':
            bg_dir = SHT_BACKGROUND_DIR
        elif dataset == 'ucf':
            bg_dir = UCF_BACKGROUND_DIR
        elif dataset == 'system':
            bg_dir = SYSTEM_BACKGROUND_DIR
        else:
            bg_dir = SHT_BACKGROUND_DIR
        
        backgrounds = []
        seen_paths = set()  # Track seen file paths to avoid duplicates
        search_lower = search.lower() if search else ''
        
        def scan_directory(dir_path, prefix=''):
            """Scan directory for images"""
            items = []
            if os.path.exists(dir_path):
                for f in sorted(os.listdir(dir_path)):
                    full_path = os.path.join(dir_path, f)
                    # Skip if already seen (avoid duplicates)
                    if full_path in seen_paths:
                        continue
                    if os.path.isfile(full_path) and f.lower().endswith(('.jpg', '.png', '.jpeg', '.webp')):
                        # Apply search filter
                        if search_lower and search_lower not in f.lower():
                            continue
                        seen_paths.add(full_path)
                        rel_name = f"{prefix}/{f}" if prefix else f
                        
                        # Read image dimensions
                        width, height = 0, 0
                        try:
                            from PIL import Image
                            with Image.open(full_path) as img:
                                width, height = img.size
                        except Exception:
                            pass
                        
                        items.append({
                            "name": f,
                            "path": full_path,
                            "relative_path": rel_name,
                            "folder": prefix,
                            "url": f"/api/video/background/{dataset}/{rel_name}",
                            "thumb_url": f"/api/video/background_thumb/{dataset}/{rel_name}",
                            "width": width,
                            "height": height
                        })
            return items
        
        if folder:
            # Scan specific folder only
            target_dir = os.path.join(bg_dir, folder)
            backgrounds = scan_directory(target_dir, folder)
        else:
            # Scan root directory only (not subdirectories) when no folder selected
            # User should select a specific folder to see its contents
            backgrounds = scan_directory(bg_dir)
        
        return backgrounds
    
    def _queue_prompt(self, workflow: dict, client_id: str = None) -> str:
        """Queue a prompt to ComfyUI"""
        prompt_id = str(uuid.uuid4())
        if client_id is None:
            client_id = str(uuid.uuid4())
        
        payload = {
            "prompt": workflow,
            "client_id": client_id,
            "prompt_id": prompt_id
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            f"{self.api_url}/prompt",
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            raise RuntimeError(f"ComfyUI rejected prompt ({e.code}): {body}")
        result = json.loads(response.read())
        
        return result.get('prompt_id', prompt_id)
    
    def _get_history(self, prompt_id: str) -> Optional[dict]:
        """Get execution history for a prompt"""
        try:
            url = f"{self.api_url}/history/{prompt_id}"
            response = urllib.request.urlopen(url, timeout=3)
            data = json.loads(response.read())
            return data.get(prompt_id)
        except:
            return None
    
    def _wait_for_completion(self, prompt_id: str, timeout: int = 600) -> dict:
        """Wait for prompt execution to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            history = self._get_history(prompt_id)
            if history:
                outputs = history.get('outputs', {})
                if outputs:
                    return {"status": "completed", "outputs": outputs}
            time.sleep(2)
        
        return {"status": "timeout", "message": f"Execution timed out after {timeout}s"}
    
    def _load_workflow(self, workflow_name: str, length: int, duration_seconds: Optional[float]) -> dict:
        """Set video length using the template's playback rate for duration requests."""
        workflow_path = os.path.join(WORKFLOW_DIR, workflow_name)
        if not os.path.exists(workflow_path):
            return {}
        with open(workflow_path) as f:
            workflow = json.load(f)
        if duration_seconds is not None:
            output = next(node["inputs"] for node in workflow.values() if node["class_type"] == "CreateVideo")
            frames = round(duration_seconds * output["fps"])
            # Wan2.1 decodes 4n + 1 frames. Trim the decoded tail before encoding the video.
            length = frames + (1 - frames) % 4
            if length != frames:
                workflow["output_frames"] = {
                    "class_type": "ImageFromBatch",
                    "inputs": {"image": output["images"], "batch_index": 0, "length": frames},
                }
                output["images"] = ["output_frames", 0]
        wan = next(node["inputs"] for node in workflow.values() if node["class_type"] == "WanVaceToVideo")
        wan["length"] = length
        return workflow
    
    def _copy_to_input(self, src_path: str) -> str:
        """Stage immutable inputs so queued jobs keep the media they selected."""
        input_dir = os.path.join(COMFYUI_PATH, "input")
        os.makedirs(input_dir, exist_ok=True)
        digest = hashlib.sha256()
        with tempfile.TemporaryDirectory(dir=input_dir) as staging:
            staged = os.path.join(staging, "media")
            with open(src_path, "rb") as source, open(staged, "wb") as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    target.write(chunk)
            filename = f"vad_{digest.hexdigest()}{os.path.splitext(src_path)[1].lower()}"
            destination = os.path.join(input_dir, filename)
            if not os.path.exists(destination):
                os.replace(staged, destination)
        return filename
    
    def text_to_video(
        self, 
        prompt: str,
        negative_prompt: str = "",
        width: int = 856,
        height: int = 480,
        length: int = 81,
        seed: int = 1,
        output_name: str = None,
        output_folder: str = None,
        duration_seconds: Optional[float] = None,
    ) -> dict:
        """Generate video from text using the T2V workflow."""
        from config import VIDEO_SYSTEM_FOLDER
        job_id = str(uuid.uuid4())
        
        # Use custom output folder or default system folder
        folder = output_folder if output_folder else VIDEO_SYSTEM_FOLDER
        
        # Use custom output name or generate one, include video/ prefix and folder path
        filename_prefix = f"video/{folder}/{output_name}" if output_name else f"video/{folder}/t2v_{job_id[:8]}"
        
        workflow = self._load_workflow("vace_t2v.json", length, duration_seconds)
        if not workflow:
            return {"error": "T2V workflow template not found"}

        for node_id, node in workflow.items():
            cls = node.get("class_type", "")
            
            if cls == "CLIPTextEncode":
                meta_title = str(node.get("_meta", {}).get("title", "")).lower()
                if "positive" in meta_title:
                    node["inputs"]["text"] = prompt
                elif "negative" in meta_title:
                    node["inputs"]["text"] = negative_prompt or "bad quality, blurry, messy"
            
            elif cls == "WanVaceToVideo":
                node["inputs"]["width"] = width
                node["inputs"]["height"] = height
            
            elif cls == "KSampler":
                if "inputs" in node and seed >= 0:
                    node["inputs"]["seed"] = 1
            
            elif cls in ("SaveAnimatedWEBP", "VHS_VideoCombine", "SaveVideo"):
                if "inputs" in node and "filename_prefix" in node["inputs"]:
                    node["inputs"]["filename_prefix"] = filename_prefix
        
        self.jobs[job_id] = {
            "type": "t2v",
            "status": "queued",
            "prompt": prompt,
            "created_at": time.time()
        }
        
        try:
            tracker = self._ensure_tracker()
            prompt_id = self._queue_prompt(workflow, client_id=tracker.client_id)
            self.jobs[job_id]["prompt_id"] = prompt_id
            self.jobs[job_id]["status"] = "running"
            
            return {
                "success": True,
                "job_id": job_id,
                "prompt_id": prompt_id,
                "message": "T2V job queued"
            }
        except Exception as e:
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = str(e)
            return {"success": False, "error": str(e)}
    
    def image_to_video(
        self,
        prompt: str,
        negative_prompt: str,
        background: str,
        dataset: str = 'sht',
        width: int = 856,
        height: int = 480,
        length: int = 81,
        seed: int = 1,
        output_name: str = None,
        output_folder: str = None,
        duration_seconds: Optional[float] = None,
    ) -> dict:
        """Generate video from image (I2V)"""
        from config import VIDEO_SYSTEM_FOLDER
        job_id = str(uuid.uuid4())
        
        # Use custom output folder or default system folder
        folder = output_folder if output_folder else VIDEO_SYSTEM_FOLDER
        
        # Use custom output name or generate one, include video/ prefix and folder path
        filename_prefix = f"video/{folder}/{output_name}" if output_name else f"video/{folder}/i2v_{job_id[:8]}"
        
        # Get background image path
        if dataset == 'sht':
            bg_path = os.path.join(SHT_BACKGROUND_DIR, background)
        else:
            bg_path = os.path.join(UCF_BACKGROUND_DIR, background)
        
        if not os.path.isfile(bg_path):
            return {"error": f"Background image not found: {background}"}
        
        # Copy background to input
        bg_filename = self._copy_to_input(bg_path)
        
        # Load I2V workflow
        workflow = self._load_workflow("vace_i2v.json", length, duration_seconds)
        if not workflow:
            return {"error": "I2V workflow template not found"}
        
        # Modify workflow for I2V
        # Update prompt node
        for node_id, node in workflow.items():
            if node.get("class_type") == "CLIPTextEncode":
                if "positive" in str(node.get("_meta", {}).get("title", "")).lower():
                    node["inputs"]["text"] = prompt
                elif "negative" in str(node.get("_meta", {}).get("title", "")).lower():
                    node["inputs"]["text"] = negative_prompt
            
            # Update image loader
            if node.get("class_type") == "LoadImage":
                node["inputs"]["image"] = bg_filename
            
            # Update video parameters
            if node.get("class_type") in ["WanVaceToVideo", "EmptyLatentVideo"]:
                if "width" in node.get("inputs", {}):
                    node["inputs"]["width"] = width
                if "height" in node.get("inputs", {}):
                    node["inputs"]["height"] = height
            
            # Update seed
            if node.get("class_type") == "KSampler" and seed >= 0:
                node["inputs"]["seed"] = 1
            
            # Set custom filename prefix for video saving nodes
            if node.get("class_type") in ["SaveAnimatedWEBP", "VHS_VideoCombine", "SaveVideo"]:
                if "inputs" in node and "filename_prefix" in node["inputs"]:
                    node["inputs"]["filename_prefix"] = filename_prefix
        
        self.jobs[job_id] = {
            "type": "i2v",
            "status": "queued",
            "prompt": prompt,
            "background": background,
            "created_at": time.time()
        }
        
        try:
            tracker = self._ensure_tracker()
            prompt_id = self._queue_prompt(workflow, client_id=tracker.client_id)
            self.jobs[job_id]["prompt_id"] = prompt_id
            self.jobs[job_id]["status"] = "running"
            
            return {
                "success": True,
                "job_id": job_id,
                "prompt_id": prompt_id,
                "message": "I2V job queued"
            }
        except Exception as e:
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = str(e)
            return {"success": False, "error": str(e)}
    
    def video_to_video(
        self,
        prompt: str,
        negative_prompt: str,
        motion_id: str,
        background: str = None,
        dataset: str = 'sht',
        width: int = 856,
        height: int = 480,
        length: int = 81,
        seed: int = 1,
        output_name: str = None,
        render_id: str = None,
        output_folder: str = None,
        duration_seconds: Optional[float] = None,
        motion_directory: Optional[str] = None,
    ) -> dict:
        """Generate video from mask video (V2V)
        
        Args:
            render_id: Specific render directory to use (e.g., 'render_yaw-60_01.jpg_sht')
            output_folder: Custom output folder name (defaults to system_generated)
        """
        from config import VIDEO_SYSTEM_FOLDER
        job_id = str(uuid.uuid4())
        
        # Use custom output folder or default system folder
        folder = output_folder if output_folder else VIDEO_SYSTEM_FOLDER
        
        # Use custom output name or generate one, include video/ prefix and folder path
        filename_prefix = f"video/{folder}/{output_name}" if output_name else f"video/{folder}/v2v_{job_id[:8]}"
        
        motion_dir = find_motion_path(motion_id, motion_directory, [MOTION_OUTPUT_DIR, SHT_MOTION_DIR, UCF_MOTION_DIR])
        
        if not motion_dir:
            return {"error": f"Motion not found: {motion_id}"}
        
        # Find render directory with mask and composite
        if render_id:
            # Use specific render if provided
            render_dir = os.path.join(motion_dir, render_id)
            if not os.path.exists(render_dir):
                return {"error": f"Render not found: {render_id}"}
        else:
            # Fallback to first available render
            render_dirs = [d for d in os.listdir(motion_dir) if d.startswith("render_")]
            if not render_dirs:
                return {"error": "No rendered mask found for this motion"}
            render_dir = os.path.join(motion_dir, render_dirs[0])
        
        composite_path = os.path.join(render_dir, "composite.mp4")
        mask_path = os.path.join(render_dir, "mask.mp4")
        
        if not os.path.exists(composite_path) or not os.path.exists(mask_path):
            return {"error": "Mask or composite video not found"}
        
        bg_path = None
        if background:
            bg_path = os.path.join(SHT_BACKGROUND_DIR if dataset == 'sht' else UCF_BACKGROUND_DIR, background)
            if not os.path.isfile(bg_path):
                return {"error": f"Background image not found: {background}"}

        if duration_seconds is None and length <= 0:
            import cv2
            cap = cv2.VideoCapture(composite_path)
            length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            if length <= 0:
                return {"error": "Could not read the reference video's frame count"}

        workflow = self._load_workflow("v2v_mask.json", length, duration_seconds)
        if not workflow:
            return {"error": "V2V workflow template not found"}
        wan = next(node["inputs"] for node in workflow.values() if node["class_type"] == "WanVaceToVideo")
        image_node, _ = wan["reference_image"]
        if bg_path:
            workflow[image_node]["inputs"]["image"] = self._copy_to_input(bg_path)
        else:
            del wan["reference_image"]
            del workflow[image_node]
        composite_filename = self._copy_to_input(composite_path)
        mask_filename = self._copy_to_input(mask_path)

        # Modify workflow for V2V
        for node_id, node in workflow.items():
            # Update prompts
            if node.get("class_type") == "CLIPTextEncode":
                title = str(node.get("_meta", {}).get("title", "")).lower()
                if "positive" in title:
                    node["inputs"]["text"] = prompt
                elif "negative" in title:
                    node["inputs"]["text"] = negative_prompt
            
            # Update video loaders (input key is "file", not "video")
            if node.get("class_type") == "LoadVideo":
                title = str(node.get("_meta", {}).get("title", "")).lower()
                # Check "mask" first since it's more specific 
                # (Node 109 title contains both "control" and "mask")
                if "mask" in title:
                    node["inputs"]["file"] = mask_filename
                else:
                    # Default: treat as composite/reference video (Node 106)
                    node["inputs"]["file"] = composite_filename
            
            # Update video parameters
            if node.get("class_type") in ["WanVaceToVideo"]:
                if "width" in node.get("inputs", {}):
                    node["inputs"]["width"] = width
                if "height" in node.get("inputs", {}):
                    node["inputs"]["height"] = height
            
            # Update seed
            if node.get("class_type") == "KSampler" and seed >= 0:
                node["inputs"]["seed"] = 1
            
            # Set custom filename prefix for video saving nodes
            if node.get("class_type") in ["SaveAnimatedWEBP", "VHS_VideoCombine", "SaveVideo"]:
                if "inputs" in node and "filename_prefix" in node["inputs"]:
                    node["inputs"]["filename_prefix"] = filename_prefix
        
        self.jobs[job_id] = {
            "type": "v2v",
            "status": "queued",
            "prompt": prompt,
            "motion_id": motion_id,
            "created_at": time.time()
        }
        
        try:
            tracker = self._ensure_tracker()
            prompt_id = self._queue_prompt(workflow, client_id=tracker.client_id)
            self.jobs[job_id]["prompt_id"] = prompt_id
            self.jobs[job_id]["status"] = "running"
            
            return {
                "success": True,
                "job_id": job_id,
                "prompt_id": prompt_id,
                "message": "V2V job queued"
            }
        except Exception as e:
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = str(e)
            return {"success": False, "error": str(e)}
    
    def get_job_status(self, job_id: str) -> dict:
        """Get status of a video generation job"""
        if job_id not in self.jobs:
            return {"error": "Job not found"}
        
        job = self.jobs[job_id]
        if job.get("status") == "running" and job.get("prompt_id"):
            history = self._get_history(job["prompt_id"])
            if history:
                status = history.get("status", {})
                if status.get("status_str") == "error":
                    job.update(status="failed", error="ComfyUI execution failed")
                elif status.get("completed") and history.get("outputs"):
                    job.update(status="completed", outputs=history["outputs"])
        return job.copy()
    
    def get_queue_status(self) -> dict:
        """Get ComfyUI queue status with progress info"""
        try:
            # Get queue info
            url = f"{self.api_url}/queue"
            response = urllib.request.urlopen(url, timeout=5)
            queue_data = json.loads(response.read())
            
            queue_running = queue_data.get('queue_running', [])
            queue_pending = queue_data.get('queue_pending', [])
            
            result = {
                "running": len(queue_running),
                "pending": len(queue_pending),
                "current_prompt_id": None,
                "progress": 0,
                "status": "idle"
            }
            
            if queue_running:
                result["status"] = "running"
                result["current_prompt_id"] = queue_running[0][1] if len(queue_running[0]) > 1 else None
            elif queue_pending:
                result["status"] = "pending"
                result["current_prompt_id"] = queue_pending[0][1] if len(queue_pending[0]) > 1 else None
            
            # Try to get progress from executing endpoint
            try:
                exec_url = f"{self.api_url}/prompt"
                exec_response = urllib.request.urlopen(exec_url, timeout=5)
                exec_data = json.loads(exec_response.read())
                if exec_data.get('exec_info', {}).get('queue_remaining', 0) > 0:
                    result["status"] = "running"
            except:
                pass
            
            return result
        except Exception as e:
            return {"error": str(e), "status": "unknown"}
    
    def _extract_video_from_outputs(self, outputs: dict) -> Optional[str]:
        """Extract video file URL from ComfyUI history outputs"""
        for node_id, node_output in outputs.items():
            # Check for videos in various formats
            for key in ['videos', 'gifs', 'images']:
                items = node_output.get(key, [])
                for item in items:
                    filename = item.get('filename', '')
                    if filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov')):
                        subfolder = item.get('subfolder', '')
                        # The API route base is already output/video/, 
                        # so strip "video/" prefix from subfolder to avoid duplication
                        if subfolder.startswith('video/'):
                            subfolder = subfolder[6:]  # Remove "video/" prefix
                        if subfolder:
                            return f"/api/video/file/{subfolder}/{filename}"
                        return f"/api/video/file/{filename}"
        return None
    
    def get_job_progress(self, prompt_id: str) -> dict:
        """Get progress for a specific job by prompt_id.
        
        Progress is derived entirely from real ComfyUI WebSocket events:
          0 %        – queued / pending
          1-9 %      – pre-sampler nodes (loading, encoding)
          10-85 %    – KSampler running (real value/max)
          86-95 %    – post-processing (VAE decode, video save)
          96-99 %    – WS says done, waiting for history
          100 %      – completed
        """
        try:
            tracker = self._ensure_tracker()
            
            # 1. Check WebSocket tracker FIRST (instant, no HTTP)
            ws = tracker.get_progress(prompt_id)
            if ws:
                if ws['status'] == 'error':
                    tracker.cleanup(prompt_id)
                    return {"status": "error", "progress": 0,
                            "message": ws.get('message', 'Execution error')}
                
                if ws['status'] == 'done':
                    # WS says done — check history for completion / video URL
                    history = self._get_history(prompt_id)
                    if history:
                        si = history.get("status", {})
                        if si.get("completed") and history.get("outputs"):
                            video_url = self._extract_video_from_outputs(history["outputs"])
                            tracker.cleanup(prompt_id)
                            result = {"status": "completed", "progress": 100, "message": "Done"}
                            if video_url:
                                result["video_url"] = video_url
                            return result
                    return {"status": "running", "progress": 98,
                            "message": "Saving output..."}
                
                # Running — compute percentage from node progress
                sampler_val = ws.get('sampler_value', 0)
                sampler_max = ws.get('sampler_max', 0)
                sampler_end = ws.get('sampler_end_time')
                nodes_fin = ws.get('nodes_finished', 0)
                nodes_tot = ws.get('nodes_total', 0)
                
                if sampler_max > 1 and sampler_val < sampler_max:
                    pct = int(10 + (sampler_val / sampler_max) * 75)
                elif sampler_end is not None:
                    post_elapsed = time.time() - sampler_end
                    pct = min(95, 86 + int(post_elapsed / 30 * 9))
                elif nodes_tot > 0:
                    pct = min(9, max(1, int(nodes_fin / max(nodes_tot, 1) * 9)))
                else:
                    pct = 1
                
                return {
                    "status": "running",
                    "progress": max(1, min(pct, 95)),
                    "message": ws.get('message', 'Generating...')
                }
            
            # 2. No WS data — quick history check (short timeout)
            history = self._get_history(prompt_id)
            if history:
                si = history.get("status", {})
                if si.get("status_str") == "error":
                    error_msg = "Generation failed"
                    for msg in si.get("messages", []):
                        if isinstance(msg, list) and len(msg) >= 2 and msg[0] == "execution_error":
                            ed = msg[1] if isinstance(msg[1], dict) else {}
                            em = ed.get("exception_message", "")
                            nt = ed.get("node_type", "")
                            if em:
                                error_msg = f"{nt}: {em.strip()}"
                            break
                    tracker.cleanup(prompt_id)
                    return {"status": "error", "progress": 0, "message": error_msg}
                if si.get("completed") and history.get("outputs"):
                    video_url = self._extract_video_from_outputs(history["outputs"])
                    tracker.cleanup(prompt_id)
                    result = {"status": "completed", "progress": 100, "message": "Done"}
                    if video_url:
                        result["video_url"] = video_url
                    return result
            
            # 3. No WS data, no history — check queue
            try:
                url = f"{self.api_url}/queue"
                response = urllib.request.urlopen(url, timeout=3)
                queue_data = json.loads(response.read())
                
                for item in queue_data.get('queue_running', []):
                    if len(item) > 1 and item[1] == prompt_id:
                        return {"status": "running", "progress": 1,
                                "message": "Running..."}
                
                for i, item in enumerate(queue_data.get('queue_pending', [])):
                    if len(item) > 1 and item[1] == prompt_id:
                        return {"status": "pending", "progress": 0,
                                "message": f"In queue (position {i + 1})"}
            except Exception:
                pass
            
            return {"status": "running", "progress": 0, "message": "Waiting..."}
        except Exception as e:
            return {"status": "error", "progress": 0, "message": str(e)}
    
    def list_video_folders(self) -> List[dict]:
        """List all video folders in ComfyUI output"""
        video_dir = os.path.join(COMFYUI_PATH, "output", "video")
        folders = [{'name': 'All', 'path': ''}]
        
        if os.path.exists(video_dir):
            for item in sorted(os.listdir(video_dir)):
                item_path = os.path.join(video_dir, item)
                if os.path.isdir(item_path):
                    # Count videos in folder
                    count = len([f for f in os.listdir(item_path) 
                               if f.lower().endswith(('.mp4', '.webm', '.avi', '.mov'))])
                    folders.append({
                        'name': item,
                        'path': item,
                        'count': count
                    })
        
        return folders
    
    def list_videos(self, folder: str = '', search: str = '') -> List[dict]:
        """List all generated videos with optional folder filter and search"""
        video_dir = os.path.join(COMFYUI_PATH, "output", "video")
        videos = []
        search_lower = search.lower() if search else ''
        
        def scan_directory(dir_path, folder_name=''):
            """Scan directory for videos"""
            items = []
            if os.path.exists(dir_path):
                for f in sorted(os.listdir(dir_path)):
                    full_path = os.path.join(dir_path, f)
                    if os.path.isfile(full_path) and f.lower().endswith(('.mp4', '.webm', '.avi', '.mov')):
                        # Apply search filter
                        if search_lower and search_lower not in f.lower():
                            continue
                        # Build URL path
                        url_path = f"{folder_name}/{f}" if folder_name else f
                        items.append({
                            "name": f,
                            "path": full_path,
                            "folder": folder_name,
                            "created": os.path.getctime(full_path),
                            "thumb_url": f"/api/video/file_thumb/{url_path}"
                        })
            return items
        
        if folder:
            # Scan specific folder
            target_dir = os.path.join(video_dir, folder)
            videos = scan_directory(target_dir, folder)
        else:
            # Scan all subfolders
            if os.path.exists(video_dir):
                for item in sorted(os.listdir(video_dir)):
                    item_path = os.path.join(video_dir, item)
                    if os.path.isdir(item_path):
                        videos.extend(scan_directory(item_path, item))
        
        return sorted(videos, key=lambda x: x["created"], reverse=True)
