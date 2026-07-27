# 🧬 AlphaDesign — AI Protein Engineering Platform

**Zero-capital, open-source protein sequence design pipeline using ESM-2 masked language models. Generates novel protein-like sequences, scores them via correct pseudo-perplexity, drafts patents, and submits to multi-million dollar contests — all running on consumer GPU with $0 cloud budget.**

---

## 🚀 What It Does

| Feature | Status |
|---------|--------|
| Generate novel protein sequences | ✅ **500 designs** (0.48—0.79 score) |
| Correct masked LM scoring | ✅ Natural > Random (GFP=0.53, Random=0.29) |
| Contest discovery | ✅ **$356M+** in live prizes tracked |
| Patent draft generation | ✅ Provisional drafts ready |
| 3D visualization dashboard | ✅ Three.js protein helix viewer |
| Daily cron automation | ✅ Runs daily at 6 AM |
| Grant applications | ✅ VitaDAO, LabDAO, ValleyDAO packages ready |

## 🧪 Results

**500 unique designs across 5 therapeutic targets:**

```
Longevity:      120 designs  (max 0.7244)
Diagnostic:     100 designs  (max 0.7306)
Enzyme:         100 designs  (max 0.7351)
Antimicrobial:  100 designs  (max 0.7277)
Antibody:        80 designs  (max 0.7928) ★ Best
```

**Example designs (top 3):**

```
MAQEALRQGVGMSVTTGPNVAIDMETGALVAFREIPLDRAYLATYACINS...  score 0.7928
MNLTISGSTTANTAAGASPLAVPSKARSIAKEPMITPFFINSSSLAPISI...  score 0.7351
MIRIEGGGSTDQMLDNIAKVHTQISQMPTVMNQMMQSLSPDERLAMEDLV...  score 0.7306
```

## ⚙️ Architecture

```
┌─────────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐
│  Designer    │───▶│  Score   │───▶│  IP      │───▶│  Submit   │
│  ESM-2 35M   │    │  Masked  │    │  Agent   │    │  →Contests│
│  Iterative   │    │  PPL     │    │  Patent  │    │  $356M+   │
│  Refinement  │    │  Correct │    │  Drafts  │    │  Pool     │
└─────────────┘    └──────────┘    └──────────┘    └───────────┘
       │                                              │
       ▼                                              ▼
┌─────────────┐                               ┌───────────┐
│  3D War     │                               │  Licensing│
│  Room Dash  │                               │  Roadmap  │
│  (Three.js) │                               │  Bio DAOs │
└─────────────┘                               └───────────┘
```

## 🔬 Scoring Improvement

**The critical fix:** ESM-2 is a BERT-like masked language model, not autoregressive. Using it left-to-right (as v1 did) produces flat scores where everything is ~1.0.

**Correct approach (v2):** Mask each position independently and compute pseudo-perplexity using only the true amino acid's log probability given bidirectional context.

```
Before (broken):      After (fixed):
GFP      → 0.80       GFP      → 0.53  ← Natural
Random   → 0.77       Random   → 0.29  ← Correctly lower
Poly-M   → 1.00       Poly-M   → 0.50  ← Penalized
```

## 💰 Monetization Paths

1. **Bio DAO Grants** — VitaDAO ($5K-$50K), LabDAO ($1K-$10K), ValleyDAO ($5K-$30K)
2. **Freelance Services** — "AI protein design" on Fiverr/Upwork ($30-50/batch)
3. **IP-NFT** — Mint designs as tradeable tokens on Molecule
4. **Contest Submissions** — $356M+ prize pool across 10 active competitions
5. **USPTO Provisional** — $75 filing converts designs to legal IP

## 📋 Requirements

- Python 3.10+
- PyTorch (CUDA 12.x)
- NVIDIA GPU with 6GB+ VRAM (tested on GTX 1060 6GB)
- Windows 11 (git-bash) / Linux

## 🛠️ Quick Start

```bash
git clone https://github.com/yourusername/alphadesign
cd alphadesign
pip install -r requirements.txt

# Generate 100 designs
python -c "
from designer.protein_designer import ProteinDesigner
d = ProteinDesigner({'model': '35m'})
designs = d.generate_protein_like_sequences(num_designs=100)
print(f'Generated {len(designs)} designs')
"

# Run full pipeline
python main.py --run

# Start daily cron
# Already configured if using Hermes Agent
```

## 📄 License

MIT — Free for all use. Designed to democratize computational protein design.

---

*Built with ESM-2, DEAP, Three.js, and a GTX 1060. Zero cloud budget. Zero wasted potential.*
