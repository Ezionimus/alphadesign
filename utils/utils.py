#!/usr/bin/env python3
"""
Utilities - GPU management, batch processing, logging, helpers
"""

import torch
import logging
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime
from contextlib import asynccontextmanager
import hashlib
import pickle

logger = logging.getLogger(__name__)


@dataclass
class GPUStats:
    """GPU utilization statistics"""
    device_id: int
    name: str
    memory_total: int
    memory_used: int
    memory_free: int
    utilization: float
    temperature: int
    power_usage: float


class GPUManager:
    """Manage GPU resources for protein design"""
    
    def __init__(self, device_ids: List[int] = None, memory_fraction: float = 0.9):
        self.device_ids = device_ids or [0] if torch.cuda.is_available() else []
        self.memory_fraction = memory_fraction
        self._setup_devices()
        
    def _setup_devices(self):
        """Configure GPU devices"""
        if not torch.cuda.is_available():
            logger.warning("CUDA not available - using CPU")
            self.devices = [torch.device("cpu")]
            return
            
        self.devices = []
        for device_id in self.device_ids:
            if device_id < torch.cuda.device_count():
                torch.cuda.set_device(device_id)
                torch.cuda.set_per_process_memory_fraction(self.memory_fraction, device_id)
                self.devices.append(torch.device(f"cuda:{device_id}"))
                logger.info(f"Configured GPU {device_id}: {torch.cuda.get_device_name(device_id)}")
            else:
                logger.warning(f"GPU {device_id} not available")
                
    def get_available_memory(self, device_id: int = 0) -> int:
        """Get available GPU memory in bytes"""
        if not torch.cuda.is_available():
            return 0
        torch.cuda.set_device(device_id)
        return torch.cuda.get_device_properties(device_id).total_memory - torch.cuda.memory_allocated(device_id)
    
    def get_stats(self) -> List[GPUStats]:
        """Get GPU statistics"""
        stats = []
        for device_id in self.device_ids:
            if device_id < torch.cuda.device_count():
                props = torch.cuda.get_device_properties(device_id)
                stats.append(GPUStats(
                    device_id=device_id,
                    name=props.name,
                    memory_total=props.total_memory,
                    memory_used=torch.cuda.memory_allocated(device_id),
                    memory_free=props.total_memory - torch.cuda.memory_allocated(device_id),
                    utilization=0,  # Would need nvidia-ml-py
                    temperature=0,
                    power_usage=0
                ))
        return stats
    
    def clear_cache(self):
        """Clear GPU memory cache"""
        if torch.cuda.is_available():
            for device_id in self.device_ids:
                if device_id < torch.cuda.device_count():
                    with torch.cuda.device(device_id):
                        torch.cuda.empty_cache()
                        torch.cuda.ipc_collect()
    
    @asynccontextmanager
    async def memory_guard(self, min_free_gb: float = 1.0):
        """Context manager to ensure minimum free memory"""
        device_id = self.device_ids[0] if self.device_ids else 0
        free_bytes = self.get_available_memory(device_id)
        free_gb = free_bytes / (1024**3)
        
        if free_gb < min_free_gb:
            self.clear_cache()
            free_bytes = self.get_available_memory(device_id)
            free_gb = free_bytes / (1024**3)
            logger.warning(f"GPU memory low: {free_gb:.1f}GB free (need {min_free_gb}GB)")
            
        try:
            yield
        finally:
            self.clear_cache()


class BatchProcessor:
    """High-throughput batch processing for protein design"""
    
    def __init__(self, 
                 batch_size: int = 32,
                 max_concurrent: int = 4,
                 gpu_manager: GPUManager = None):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.gpu_manager = gpu_manager or GPUManager()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
    async def process_batch(self, 
                           items: List[Any],
                           process_fn: Callable,
                           *args, **kwargs) -> List[Any]:
        """Process items in batches with concurrency control"""
        results = []
        
        # Split into batches
        batches = [items[i:i + self.batch_size] for i in range(0, len(items), self.batch_size)]
        
        async def process_single_batch(batch):
            async with self.semaphore:
                async with self.gpu_manager.memory_guard():
                    return await process_fn(batch, *args, **kwargs)
        
        # Process batches concurrently
        tasks = [process_single_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Batch failed: {result}")
                results.append(None)
            else:
                results.extend(result if isinstance(result, list) else [result])
                
        return results
    
    async def process_stream(self,
                            stream: AsyncGenerator,
                            process_fn: Callable,
                            *args, **kwargs) -> AsyncGenerator:
        """Process streaming input"""
        batch = []
        async for item in stream:
            batch.append(item)
            if len(batch) >= self.batch_size:
                async with self.semaphore:
                    async with self.gpu_manager.memory_guard():
                        results = await process_fn(batch, *args, **kwargs)
                        for r in results:
                            yield r
                batch = []
                
        # Process remaining
        if batch:
            async with self.semaphore:
                async with self.gpu_manager.memory_guard():
                    results = await process_fn(batch, *args, **kwargs)
                    for r in results:
                        yield r


class StructuredLogger:
    """Structured logging for pipeline tracking"""
    
    def __init__(self, name: str, log_dir: Path = None):
        self.name = name
        self.log_dir = log_dir or Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        self._setup_logger()
        
    def _setup_logger(self):
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)
        
        # File handler
        log_file = self.log_dir / f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Format
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        
    def log_design(self, design_id: str, metrics: Dict):
        """Log design metrics"""
        self.logger.info(f"DESIGN | {design_id} | {json.dumps(metrics)}")
        
    def log_contest(self, contest: str, action: str, details: Dict):
        """Log contest activity"""
        self.logger.info(f"CONTEST | {contest} | {action} | {json.dumps(details)}")
        
    def log_patent(self, patent_id: str, action: str, details: Dict):
        """Log patent activity"""
        self.logger.info(f"PATENT | {patent_id} | {action} | {json.dumps(details)}")
        
    def log_pipeline(self, stage: str, status: str, metrics: Dict = None):
        """Log pipeline stage"""
        msg = f"PIPELINE | {stage} | {status}"
        if metrics:
            msg += f" | {json.dumps(metrics)}"
        self.logger.info(msg)


class DesignCache:
    """Cache for protein designs with deduplication"""
    
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("cache/designs")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / "index.json"
        self.index = self._load_index()
        
    def _load_index(self) -> Dict:
        if self.index_file.exists():
            with open(self.index_file) as f:
                return json.load(f)
        return {}
    
    def _save_index(self):
        with open(self.index_file, "w") as f:
            json.dump(self.index, f, indent=2)
    
    def _sequence_hash(self, sequence: str) -> str:
        return hashlib.sha256(sequence.encode()).hexdigest()[:16]
    
    def get(self, sequence: str) -> Optional[Dict]:
        """Get cached design by sequence"""
        h = self._sequence_hash(sequence)
        if h in self.index:
            cache_file = self.cache_dir / f"{h}.pkl"
            if cache_file.exists():
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
        return None
    
    def put(self, sequence: str, design: Dict):
        """Cache a design"""
        h = self._sequence_hash(sequence)
        cache_file = self.cache_dir / f"{h}.pkl"
        with open(cache_file, "wb") as f:
            pickle.dump(design, f)
        self.index[h] = {
            "sequence": sequence,
            "length": len(sequence),
            "plddt": design.get("plddt"),
            "created": datetime.now().isoformat()
        }
        self._save_index()
    
    def deduplicate(self, designs: List[Dict]) -> List[Dict]:
        """Remove duplicate sequences"""
        seen = set()
        unique = []
        for d in designs:
            h = self._sequence_hash(d["sequence"])
            if h not in seen:
                seen.add(h)
                unique.append(d)
        return unique
    
    def stats(self) -> Dict:
        return {
            "cached_designs": len(self.index),
            "total_sequences": sum(1 for _ in self.index),
            "cache_size_mb": sum(f.stat().st_size for f in self.cache_dir.glob("*.pkl")) / (1024**2)
        }


def setup_logging(log_level: str = "INFO", log_dir: str = "logs"):
    """Setup global logging"""
    Path(log_dir).mkdir(exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        handlers=[
            logging.FileHandler(Path(log_dir) / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"),
            logging.StreamHandler()
        ]
    )


def load_json_safe(path: Path) -> Any:
    """Safely load JSON file"""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to load JSON from {path}: {e}")
        return None


def save_json_safe(data: Any, path: Path):
    """Safely save JSON file"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    tmp_path.replace(path)


async def run_with_timeout(coro, timeout: float):
    """Run coroutine with timeout"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Operation timed out after {timeout}s")
        raise
