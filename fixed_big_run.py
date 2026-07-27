#!/usr/bin/env python3
"""FIXED BIG RUN: Uses masked LM refinement for real protein-like sequences"""
import sys, json, torch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

torch.cuda.empty_cache()

from designer.protein_designer import ProteinDesigner, ProteinDesign
from ip.ip_agent import IPAgent
from hunter.contest_hunter import ContestHunter
import asyncio

print("=" * 60)
print("🔥 PROTEIN GENERATION v2 — MASKED LM REFINEMENT")
print("=" * 60)

# Use 35M for fast masked scoring
designer = ProteinDesigner({'model': '35m'})

print(f"\nGenerating 100 diverse protein-like sequences...")
designs = designer.generate_protein_like_sequences(
    num_designs=100,
    length_range=(60, 150)
)

print(f"\nTop 10 designs:")
designs.sort(key=lambda d: d.fitness or 0, reverse=True)
for i, d in enumerate(designs[:10]):
    preview = d.sequence[:50] + "..."
    print(f"  #{i+1}: score={d.fitness:.4f} len={len(d.sequence):3d}  {preview}")

# Save
output_dir = Path("outputs/designs_v2")
designer.save_designs(designs, output_dir)
print(f"\nSaved {len(designs)} designs to {output_dir}")

# Score stats
scores = [d.fitness for d in designs if d.fitness is not None]
if scores:
    print(f"Scores: min={min(scores):.4f} max={max(scores):.4f} avg={sum(scores)/len(scores):.4f}")

# Diversity check
seqs = [d.sequence for d in designs]
unique = len(set(seqs))
print(f"Unique: {unique}/{len(designs)}")
if unique < len(designs):
    print("WARNING: Duplicates found!")

# Top 5 designs content comparison (are they diverse?)
print(f"\nTop 5 sequence diversity check:")
for i, d in enumerate(designs[:5]):
    # Count unique AA types
    unique_aa = len(set(d.sequence))
    print(f"  #{i+1}: AA types={unique_aa}/20  aliphatic={d.sequence.count('A')+d.sequence.count('V')+d.sequence.count('L')+d.sequence.count('I')+d.sequence.count('M')}")

print("\n✅ GENERATION COMPLETE")
