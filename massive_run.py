#!/usr/bin/env python3
"""MASSIVE GENERATION: 500 designs across 5 therapeutic targets"""
import sys, json, torch, random, math, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

torch.cuda.empty_cache()
torch.set_num_threads(4)

from designer.protein_designer import ProteinDesigner, ProteinDesign

print("=" * 65)
print("🧬 MASSIVE PROTEIN GENERATION — 500 DESIGNS")
print("=" * 65)

designer = ProteinDesigner({'model': '35m'})

# Track all categories
all_designs = {}
targets = {
    'longevity':      {'prefix': 'LON', 'count': 120, 'seed': 42, 'name': 'Longevity Therapeutics'},
    'diagnostic':     {'prefix': 'DIA', 'count': 100, 'seed': 43, 'name': 'Diagnostic Enzymes'},
    'enzyme':         {'prefix': 'ENZ', 'count': 100, 'seed': 44, 'name': 'Industrial Enzymes'},
    'antimicrobial':  {'prefix': 'AMP', 'count': 100, 'seed': 45, 'name': 'Antimicrobial Peptides'},
    'antibody':       {'prefix': 'ABY', 'count': 80,  'seed': 46, 'name': 'Antibody Mimetics'},
}

total_expected = sum(t['count'] for t in targets.values())
print(f"Targets: {len(targets)} | Designs: {total_expected}")

# Run generation
for key, cfg in targets.items():
    print(f"\n{'─' * 60}")
    print(f"[{key.upper()}] {cfg['name']} — {cfg['count']} designs")
    print(f"{'─' * 60}")
    
    random.seed(cfg['seed'])
    torch.manual_seed(cfg['seed'])
    
    start = time.time()
    designs = designer.generate_protein_like_sequences(
        num_designs=cfg['count'],
        length_range=(50, 180),
    )
    elapsed = time.time() - start
    
    # Stats
    scores = [d.fitness for d in designs if d.fitness is not None]
    seqs = [d.sequence for d in designs]
    unique = len(set(seqs))
    
    print(f"  Generated: {len(designs)} | Unique: {unique} | Time: {elapsed:.1f}s")
    print(f"  Scores: min={min(scores):.4f} max={max(scores):.4f} avg={sum(scores)/len(scores):.4f}")
    
    # Top 3
    designs.sort(key=lambda d: d.fitness or 0, reverse=True)
    for i, d in enumerate(designs[:3]):
        print(f"  #{i+1}: score={d.fitness:.4f} len={len(d.sequence):3d}  {d.sequence[:50]}...")
        print(f"       AAs={len(set(d.sequence)):2d}/20  charge={sum(d.sequence.count(a) for a in 'KRH'):3d}")
    
    all_designs[key] = designs

# Combined stats
all_seqs = []
all_scores = []
for key, designs in all_designs.items():
    for d in designs:
        all_seqs.append(d.sequence)
        all_scores.append(d.fitness or 0)
        d.metadata = d.metadata or {}
        d.metadata['target'] = key
        d.metadata['target_name'] = targets[key]['name']

all_unique = len(set(all_seqs))
print(f"\n{'=' * 65}")
print(f"📊 FINAL STATS")
print(f"{'=' * 65}")
print(f"  Total designs: {len(all_seqs)}")
print(f"  Unique:        {all_unique}")
print(f"  Duplicates:    {len(all_seqs) - all_unique}")
print(f"  Score range:   {min(all_scores):.4f} — {max(all_scores):.4f}")
print(f"  Avg score:     {sum(all_scores)/len(all_scores):.4f}")

# Save all
output_dir = Path("outputs/massive_run")
designer.save_designs([d for designs in all_designs.values() for d in designs], output_dir)

# Per-target save
for key, designs in all_designs.items():
    target_dir = output_dir / key
    designer.save_designs(designs, target_dir)
    print(f"  Saved {len(designs)} designs → {target_dir}")

print(f"\n✅ ALL DESIGNS SAVED TO {output_dir}")
