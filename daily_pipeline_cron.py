#!/usr/bin/env python3
"""Daily protein contest automation cron job.
Discovers contests, generates designs, files IP, prepares submissions.
"""
import sys, asyncio, json, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from main import ProteinContestPipeline

logging.basicConfig(level=logging.INFO)

print("=" * 60)
print("PROTEIN CONTEST AUTOMATION - DAILY RUN")
print("=" * 60)

config = {
    'gpu': {'device_id': 0, 'memory_fraction': 0.85},
    'design': {'target_fold': 'novel', 'constraints': {'length_range': [80, 150]}},
    'evolution': {'enabled': True, 'generations': 10, 'population': 50},
    'contests': {'min_prize': 0},
    'ip': {'auto_file': False, 'portfolio_path': 'ip_portfolio'},
    'pipeline': {'design_batch_size': 30, 'max_contests_per_cycle': 5}
}

pipeline = ProteinContestPipeline(config)
result = asyncio.run(pipeline.run_full_cycle())

print()
print("=" * 60)
print("DAILY RUN COMPLETE")
print("=" * 60)
print(f"  New Designs:     {result['designs']}")
print(f"  Patents Filed:   {result['patents']}")
print(f"  Submissions:     {result['submissions']}")
print(f"  Portfolio Value: ${result['portfolio'].get('estimated_value', 0):,.0f}")

# Also output a summary for cron delivery
print()
print("---SUMMARY---")
print(json.dumps(result['stats']))
