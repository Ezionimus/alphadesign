#!/usr/bin/env python3
"""
Utilities - GPU management, batch processing, logging
"""

import torch
import logging
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


@dataclass
class GPUStats:
    """GPU utilization statistics"""
    device_id: int
    name: str
    memory_total: int
    memory_used: int
    memory_free: int
    utilization: float
    temperature: float
    power_draw: float


class GPUManager:
    """Manage GPU resources for protein design"""
    
    def __init__(self):
        self.devices = self._discover_devices()
        self._lock = threading.Lock()
        self._allocations: Dict[int, List[str]] = {}
        
    def _discover_devices(self) -> List[GPUStats]:
        """Discover available GPUs"""
        devices = []
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                devices.append(GPUStats(
                    device_id=i,
                    name=props.name,
                    memory_total=props.total_memory,
                    memory_used=0,
                    memory_free=props.total_memory,
                    utilization=0.0,
                    temperature=0.0,
                    power_draw=0.0
                ))
        return devices
    
    def get_best_device(self, min_memory_gb: float = 2.0) -> Optional[int]:
        """Get device with most free memory"""
        with self._lock:
            for device in sorted(self.devices, key=lambda d: d.memory_free, reverse=True):
                if device.memory_free >= min_memory_gb * 1024**3:
                    return device.device_id
        return None
    
    def allocate(self, device_id: int, task_name: str):
        """Allocate GPU for task"""
        with self._lock:
            if device_id not in self._allocations:
                self._allocations[device_id] = []
            self._allocations[device_id].append(task_name)
            
            # Update memory estimate
            for d in self.devices:
                if d.device_id == device_id:
                    d.memory_free -= 1024**3  # Estimate 1GB per task
                    
    def release(self, device_id: int, task_name: str):
        """Release GPU allocation"""
        with self._lock:
            if device_id in self._allocations and task_name in self._allocations[device_id]:
                self._allocations[device_id].remove(task_name)
                
            for d in self.devices:
                if d.device_id == device_id:
                    d.memory_free += 1024**3
                    
    def get_stats(self) -> List[GPUStats]:
        """Get current GPU stats"""
        # Update with real stats if nvidia-ml-py available
        try:
            import pynvml
            pynvml.nvmlInit()
            for i, device in enumerate(self.devices):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                
                device.memory_used = mem.used
                device.memory_free = mem.free
                device.utilization = util.gpu
                device.temperature = temp
        except:
            pass  # pynvml not available
        return self.devices


class BatchProcessor:
    """High-throughput batch processing for protein design"""
    
    def __init__(self, max_workers: int = 4, gpu_manager: GPUManager = None):
        self.max_workers = max_workers
        self.gpu_manager = gpu_manager or GPUManager()
        self.results = []
        self.errors = []
        
    def process_batch(self, 
                      items: List[Any],
                      process_fn: Callable,
                      batch_size: int = None,
                      progress_callback: Callable = None) -> List[Any]:
        """Process items in batches with GPU management"""
        batch_size = batch_size or self.max_workers
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i+batch_size]
            
            # Submit batch to thread pool
            with ThreadPoolExecutor(max_workers=min(len(batch), self.max_workers)) as executor:
                futures = {}
                
                for item in batch:
                    device_id = self.gpu_manager.get_best_device()
                    if device_id is not None:
                        self.gpu_manager.allocate(device_id, f"batch_{i}")
                        futures[executor.submit(self._process_with_gpu, process_fn, item, device_id)] = item
                    else:
                        # CPU fallback
                        futures[executor.submit(process_fn, item)] = item
                
                # Collect results
                for future in as_completed(futures):
                    item = futures[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        self.errors.append({"item": str(item), "error": str(e)})
                        results.append(None)
                        
                    # Release GPU
                    for device in self.gpu_manager.devices:
                        if f"batch_{i}" in self.gpu_manager._allocations.get(device.device_id, []):
                            self.gpu_manager.release(device.device_id, f"batch_{i}")
                            
            if progress_callback:
                progress_callback(i + len(batch), len(items))
                
        return results
    
    def _process_with_gpu(self, fn: Callable, item: Any, device_id: int) -> Any:
        """Process item on specific GPU"""
        torch.cuda.set_device(device_id)
        with torch.cuda.device(device_id):
            return fn(item)


class StructuredLogger:
    """Structured JSON logging for pipeline tracking"""
    
    def __init__(self, log_dir: Path = None, level: int = logging.INFO):
        # Handle string or Path arguments
        if log_dir is not None and not isinstance(log_dir, Path):
            log_dir = Path(log_dir)
        self.log_dir = log_dir or Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger("protein_pipeline")
        self.logger.setLevel(level)
        
        # JSON file handler
        json_handler = logging.FileHandler(self.log_dir / "pipeline.jsonl")
        json_handler.setFormatter(JsonFormatter())
        self.logger.addHandler(json_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))
        self.logger.addHandler(console_handler)
        
    def log_pipeline(self, stage: str, status: str, extra: Dict = None):
        """Log a pipeline stage event"""
        self.logger.info(f"pipeline_{stage}_{status}", extra={
            "event": "pipeline",
            "stage": stage,
            "status": status,
            **(extra or {})
        })

    def log_design(self, design_data: Dict):
        """Log a design event"""
        self.logger.info("design_created", extra=design_data)
        
    def log_contest(self, contest_name: str, status: str = None, extra: Dict = None):
        """Log a contest event"""
        if isinstance(contest_name, dict):
            self.logger.info("contest_event", extra=contest_name)
        else:
            data = {"contest": contest_name}
            if status:
                data["status"] = status
            if extra:
                data.update(extra)
            self.logger.info("contest_event", extra=data)
        
    def log_patent(self, patent_data: Dict):
        """Log a patent event"""
        self.logger.info("patent_event", extra=patent_data)
        
    def log_metric(self, name: str, value: float, tags: Dict = None):
        """Log a metric"""
        self.logger.info("metric", extra={
            "metric_name": name,
            "metric_value": value,
            "tags": tags or {}
        })


class JsonFormatter(logging.Formatter):
    """Format logs as JSON lines"""
    
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "filename", "funcName",
                          "levelname", "levelno", "lineno", "module", "msecs",
                          "message", "name", "pathname", "process", "processName",
                          "relativeCreated", "thread", "threadName", "exc_info",
                          "exc_text", "stack_info"]:
                log_data[key] = value
                
        return json.dumps(log_data)


class CheckpointManager:
    """Manage pipeline checkpoints for resumability"""
    
    def __init__(self, checkpoint_dir: Path = None):
        self.checkpoint_dir = checkpoint_dir or Path("checkpoints")
        self.checkpoint_dir.mkdir(exist_ok=True)
        
    def save(self, stage: str, data: Dict, metadata: Dict = None):
        """Save checkpoint"""
        checkpoint = {
            "stage": stage,
            "timestamp": time.time(),
            "data": data,
            "metadata": metadata or {}
        }
        
        filepath = self.checkpoint_dir / f"checkpoint_{stage}_{int(time.time())}.json"
        with open(filepath, "w") as f:
            json.dump(checkpoint, f, indent=2, default=str)
            
        # Keep only latest 5 per stage
        self._cleanup_stage(stage)
        return filepath
    
    def _cleanup_stage(self, stage: str):
        """Remove old checkpoints for stage"""
        checkpoints = sorted(self.checkpoint_dir.glob(f"checkpoint_{stage}_*.json"))
        for cp in checkpoints[:-5]:
            cp.unlink()
            
    def load_latest(self, stage: str) -> Optional[Dict]:
        """Load latest checkpoint for stage"""
        checkpoints = sorted(self.checkpoint_dir.glob(f"checkpoint_{stage}_*.json"))
        if not checkpoints:
            return None
            
        with open(checkpoints[-1]) as f:
            return json.load(f)
            
    def load_all_stages(self) -> Dict[str, Dict]:
        """Load latest checkpoint for each stage"""
        stages = {}
        for cp in self.checkpoint_dir.glob("checkpoint_*.json"):
            stage = cp.name.split("_")[1]
            if stage not in stages:
                with open(cp) as f:
                    stages[stage] = json.load(f)
        return stages


class ConfigManager:
    """Manage configuration with environment overrides"""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path("config.yaml")
        self.config = self._load()
        
    def _load(self) -> Dict:
        """Load config from YAML with env var overrides"""
        import os
        import yaml
        
        config = {}
        if self.config_path.exists():
            with open(self.config_path) as f:
                config = yaml.safe_load(f) or {}
                
        # Override with environment variables
        for key, value in os.environ.items():
            if key.startswith("PROTEIN_"):
                # PROTEIN_DESIGN_BATCH_SIZE -> design.batch_size
                path = key[8:].lower().split("_")
                self._set_nested(config, path, self._parse_value(value))
                
        return config
    
    def _set_nested(self, d: Dict, path: List[str], value: Any):
        """Set nested dictionary value"""
        for key in path[:-1]:
            d = d.setdefault(key, {})
        d[path[-1]] = value
        
    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type"""
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        try:
            return int(value)
        except:
            try:
                return float(value)
            except:
                return value
                
    def get(self, path: str, default: Any = None) -> Any:
        """Get config value by dot-notation path"""
        keys = path.split(".")
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def save(self):
        """Save config to file"""
        import yaml
        with open(self.config_path, "w") as f:
            yaml.dump(self.config, f, default_flow_style=False)
