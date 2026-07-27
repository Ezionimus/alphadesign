#!/usr/bin/env python3
"""
BIG RUN: Generate 200+ diverse protein designs, file patents, submit to top contests
Uses ESM-2 650M for high-quality scoring
"""
import sys, asyncio, json, logging, random, torch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("big_run")

print("=" * 60)
print("🔥 PROTEIN CONTEST AUTOMATION - BIG RUN (650M)")
print("=" * 60)

# 1. DESIGN - target different biological functions
TARGETS = [
    ("longevity", "therapeutic protein for cellular repair", [80, 150]),
    ("diagnostic", "biosensor protein with binding pocket", [80, 120]),
    ("enzyme", "novel biocatalyst for industrial process", [100, 200]),
    ("antibody mimetic", "small protein binder for therapeutic target", [60, 100]),
    ("antimicrobial", "novel antimicrobial peptide", [30, 60]),
]

from designer.protein_designer import ProteinDesigner, ProteinDesign

# Force 650M model
designer = ProteinDesigner({
    'device_id': 0,
    'memory_fraction': 0.9,
    'model': '650m'  # Try to load 650M
})

model_size = designer.models.get("model_size", "unknown")
print(f"\nModel loaded: {model_size}")
print(f"VRAM used: {torch.cuda.memory_allocated()/1e9:.2f}GB" if __import__('torch').cuda.is_available() else "")

# Generate designs for each target
all_designs = []
for target_name, target_desc, length_range in TARGETS:
    print(f"\n{'='*40}")
    print(f"Designing for: {target_name}")
    print(f"Description: {target_desc}")
    
    designs = designer.design_de_novo(
        target_fold=target_name,
        constraints={"length_range": length_range},
        num_designs=40
    )
    
    # Label each design with its target
    for d in designs:
        d.metadata["target"] = target_name
        d.metadata["target_description"] = target_desc
    
    all_designs.extend(designs)
    print(f"Got {len(designs)} designs for {target_name}")

# Deduplicate across targets
seen = set()
unique_designs = []
for d in all_designs:
    if d.sequence not in seen:
        seen.add(d.sequence)
        unique_designs.append(d)

print(f"\n{'='*60}")
print(f"Total unique designs: {len(unique_designs)}")

# Sort by fitness
unique_designs.sort(key=lambda x: x.fitness or 0, reverse=True)
for i, d in enumerate(unique_designs[:5]):
    tgt = d.metadata.get("target", "unknown") if d.metadata else "unknown"
    print(f"  #{i+1}: score={d.fitness:.4f} len={len(d.sequence):3d} target={tgt}")

# Save
output_dir = Path("outputs/designs_bigrun")
designer.save_designs(unique_designs, output_dir)
print(f"\nSaved {len(unique_designs)} designs to {output_dir}")

# 2. IP PHASE - Track and patent
from ip.ip_agent import IPAgent
ip = IPAgent({"portfolio_path": "ip_portfolio"})

design_dicts = []
for d in unique_designs:
    dd = d.__dict__.copy()
    if d.metadata:
        dd["metadata"] = dict(d.metadata)
    else:
        dd["metadata"] = {}
    design_dicts.append(dd)

design_ids = ip.track_designs(design_dicts)
print(f"Tracked {len(design_ids)} designs")

# Generate patents per target
from collections import defaultdict
by_target = defaultdict(list)
for did, dd in zip(design_ids, design_dicts):
    tgt = dd.get("metadata", {}).get("target", "unknown")
    by_target[tgt].append(did)

patents = []
for target, ids in by_target.items():
    batch_size = 20
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i+batch_size]
        patent = ip.generate_provisional_patent(batch)
        patents.append(patent)
        print(f"Patent for {target}: {patent.title[:60]}...")

if patents:
    print(f"Generated {len(patents)} patents")

# 3. SUBMIT to top contests
from hunter.contest_hunter import ContestHunter
hunter = ContestHunter({"min_prize": 0})

# Refresh contest list
new_contests = hunter.discover_contests()
active = hunter.get_active_contests()

# Sort by prize
active.sort(key=lambda c: c.prize, reverse=True)

print(f"\n{'='*60}")
print(f"SUBMITTING TO TOP CONTESTS")
print(f"{'='*60}")
submissions = []
for contest in active[:5]:
    sub = hunter.prepare_submission(design_dicts, contest)
    result = asyncio.run(hunter.submit(sub, contest))
    submissions.append(result)
    print(f"  ✓ {contest.name}: {sub.submission_id} (${contest.prize:,.0f})")

print(f"\n{'='*60}")
print(f"🔥 BIG RUN COMPLETE")
print(f"{'='*60}")
print(f"  Designs: {len(unique_designs)}")
print(f"  Patents: {len(patents)}")
print(f"  Submissions: {len(submissions)}")
print(f"  Top contest prize: ${active[0].prize:,.0f}" if active else "")
