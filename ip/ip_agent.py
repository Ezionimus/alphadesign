#!/usr/bin/env python3
"""
IP Agent - Automated patent drafting, prior art search, and portfolio management
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class DesignRecord:
    """Record of a protein design for IP purposes"""
    sequence: str
    structure_pdb: Optional[str]
    plddt: Optional[float]
    fitness: Optional[float]
    method: str
    target: str
    constraints: Dict
    created_at: str
    design_id: str
    contest_submissions: List[str] = None
    patent_filed: bool = False
    patent_number: Optional[str] = None


@dataclass
class PatentDraft:
    """Provisional patent draft"""
    title: str
    inventors: List[str]
    description: str
    claims: List[str]
    abstract: str
    drawings: List[str]
    sequence_listings: List[Dict]
    filed_date: Optional[str]
    application_number: Optional[str]
    design_ids: List[str]


class IPAgent:
    """Manages IP for protein designs"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.auto_file = self.config.get("auto_file_provisional", False)
        self.jurisdictions = self.config.get("jurisdictions", ["US"])
        self.portfolio_path = Path(self.config.get("portfolio_path", "ip_portfolio"))
        self.portfolio_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing portfolio
        self.designs: Dict[str, DesignRecord] = {}
        self.patents: Dict[str, PatentDraft] = {}
        self._load_portfolio()
        
    def _load_portfolio(self):
        """Load existing portfolio from disk"""
        designs_file = self.portfolio_path / "designs.json"
        if designs_file.exists():
            with open(designs_file) as f:
                data = json.load(f)
                self.designs = {k: DesignRecord(**v) for k, v in data.items()}
                
        patents_file = self.portfolio_path / "patents.json"
        if patents_file.exists():
            with open(patents_file) as f:
                data = json.load(f)
                self.patents = {k: PatentDraft(**v) for k, v in data.items()}
                
    def _save_portfolio(self):
        """Save portfolio to disk"""
        designs_file = self.portfolio_path / "designs.json"
        with open(designs_file, "w") as f:
            json.dump({k: asdict(v) for k, v in self.designs.items()}, f, indent=2)
            
        patents_file = self.portfolio_path / "patents.json"
        with open(patents_file, "w") as f:
            json.dump({k: asdict(v) for k, v in self.patents.items()}, f, indent=2)
    
    def track_designs(self, designs: List[Dict], contest: str = None) -> List[str]:
        """Track new designs for IP purposes"""
        design_ids = []
        
        for i, d in enumerate(designs):
            design_id = f"DES_{datetime.now().strftime('%Y%m%d')}_{len(self.designs)+i:04d}"
            
            record = DesignRecord(
                sequence=d["sequence"],
                structure_pdb=d.get("structure"),
                plddt=d.get("plddt"),
                fitness=d.get("fitness"),
                method=d.get("metadata", {}).get("method", "unknown"),
                target=d.get("metadata", {}).get("target", "unknown"),
                constraints=d.get("metadata", {}).get("constraints", {}),
                created_at=datetime.now().isoformat(),
                design_id=design_id,
                contest_submissions=[contest] if contest else []
            )
            
            self.designs[design_id] = record
            design_ids.append(design_id)
            
        self._save_portfolio()
        logger.info(f"Tracked {len(design_ids)} new designs")
        return design_ids
    
    def generate_provisional_patent(self, design_ids: List[str]) -> PatentDraft:
        """Generate provisional patent application from designs"""
        
        designs = [self.designs[did] for did in design_ids if did in self.designs]
        if not designs:
            raise ValueError("No valid design IDs provided")
            
        # Generate patent title
        targets = set(d.target for d in designs)
        methods = set(d.method for d in designs)
        title = f"Novel {', '.join(targets)} Proteins and Methods of Design Thereof"
        
        # Generate description
        description = self._generate_description(designs)
        
        # Generate claims
        claims = self._generate_claims(designs)
        
        # Generate abstract
        abstract = self._generate_abstract(designs)
        
        # Generate sequence listing
        sequence_listings = self._generate_sequence_listing(designs)
        
        # Create patent draft
        patent = PatentDraft(
            title=title,
            inventors=["AI System (Automated Design)", "Human Supervisor"],
            description=description,
            claims=claims,
            abstract=abstract,
            drawings=[],
            sequence_listings=sequence_listings,
            filed_date=None,
            application_number=None,
            design_ids=design_ids
        )
        
        patent_id = f"PROV_{datetime.now().strftime('%Y%m%d')}_{len(self.patents)+1:04d}"
        self.patents[patent_id] = patent
        self._save_portfolio()
        
        # Save individual patent file
        patent_file = self.portfolio_path / "patents" / f"{patent_id}.md"
        patent_file.parent.mkdir(exist_ok=True)
        with open(patent_file, "w") as f:
            f.write(self._format_patent(patent))
            
        logger.info(f"Generated provisional patent: {patent_id}")
        return patent
    
    def _generate_description(self, designs: List[DesignRecord]) -> str:
        """Generate detailed patent description"""
        desc = f"""
# {designs[0].target.capitalize()} Protein Designs - Technical Description

## Field of the Invention
The present invention relates to novel {', '.join(set(d.target for d in designs))} proteins, 
nucleic acids encoding said proteins, vectors comprising said nucleic acids, host cells 
comprising said vectors, and methods of designing, producing, and using said proteins.

## Background
Traditional protein engineering relies on rational design or directed evolution, which are 
limited by the vast sequence space and the difficulty of predicting structure-function 
relationships. The present invention overcomes these limitations through AI-driven de novo 
protein design combined with evolutionary optimization.

## Summary of the Invention
The invention provides:
1. Novel protein sequences with {designs[0].target} activity
2. Methods for designing proteins using AI structure prediction and sequence optimization
3. Evolutionary algorithms for multi-objective protein optimization
4. Compositions and kits comprising the novel proteins

## Detailed Description

### AI-Driven Protein Design
The proteins of the invention were designed using a computational pipeline comprising:
1. **Structure Prediction**: AlphaFold2/ESMFold for 3D structure prediction
2. **Sequence Design**: ProteinMPNN for inverse folding
3. **De Novo Design**: RFdiffusion/AlphaFold hallucination for novel backbones
5. **Evolutionary Optimization**: Genetic algorithms for multi-objective optimization

### Protein Sequences
The following novel protein sequences are disclosed:
"""
        for d in designs:
            desc += f"""
#### Design {d.design_id}
**Sequence:** {d.sequence}
**Length:** {len(d.sequence)} amino acids
**Predicted pLDDT:** {d.plddt or 'N/A'}
**Fitness Score:** {d.fitness or 'N/A'}
**Design Method:** {d.method}
**Target:** {d.target}
**Constraints:** {json.dumps(d.constraints)}
"""
        desc += """
### Production Methods
The proteins may be produced by recombinant expression in suitable host cells including
E. coli, yeast, mammalian cells, or cell-free systems.

### Applications
The novel proteins find use in:
- Therapeutic applications
- Industrial biocatalysis
- Biosensors and diagnostics
- Research tools
- Agricultural applications
"""
        return desc
    
    def _generate_claims(self, designs: List[DesignRecord]) -> List[str]:
        """Generate patent claims"""
        claims = []
        num_seqs = len(designs)
        
        # Claim 1: Composition of matter
        claims.append(
            f"1. An isolated protein comprising an amino acid sequence selected from the "
            f"group consisting of SEQ ID NOs: 1-{num_seqs}."
        )
        
        # Claim 2: Variants
        claims.append(
            f"2. The protein of claim 1, wherein the amino acid sequence has at least 80%, "
            f"85%, 90%, 95%, 98%, or 99% identity to any of SEQ ID NOs: 1-{num_seqs}."
        )
        
        # Claim 3: Nucleic acid
        claims.append(
            f"3. An isolated nucleic acid encoding the protein of claim 1."
        )
        
        # Claim 4: Vector
        claims.append(
            f"4. A vector comprising the nucleic acid of claim 3."
        )
        
        # Claim 5: Host cell
        claims.append(
            f"5. A host cell comprising the vector of claim 4."
        )
        
        # Claim 6: Method of production
        claims.append(
            f"6. A method of producing a protein, comprising culturing the host cell of claim 5 "
            f"under conditions suitable for protein expression, and optionally recovering the protein."
        )
        
        # Claim 7: Method of design
        claims.append(
            f"7. A computer-implemented method for designing a protein with {designs[0].target} activity, "
            f"comprising: (a) predicting a three-dimensional structure using a deep learning model; "
            f"(b) designing amino acid sequences compatible with said structure using a neural network; "
            f"(c) optimizing sequences via evolutionary algorithms; (d) selecting optimized sequences."
        )
        
        return claims
    
    def _generate_abstract(self, designs: List[DesignRecord]) -> str:
        """Generate patent abstract"""
        target = designs[0].target
        num = len(designs)
        return (
            f"The invention provides {num} novel {target} protein sequences designed using "
            f"artificial intelligence-driven computational methods. The proteins were generated "
            f"via de novo structure prediction (AlphaFold2/ESMFold), inverse folding (ProteinMPNN), "
            f"and evolutionary optimization (genetic algorithms). The sequences exhibit predicted "
            f"pLDDT scores of {min(d.plddt for d in designs if d.plddt):.1f}-"
            f"{max(d.plddt for d in designs if d.plddt):.1f} and are suitable for therapeutic, "
            f"industrial, and research applications. Also provided are nucleic acids encoding said "
            f"proteins, expression vectors, host cells, and methods of production and use."
        )
    
    def _generate_sequence_listing(self, designs: List[DesignRecord]) -> List[Dict]:
        """Generate sequence listing for patent"""
        listings = []
        for i, d in enumerate(designs, 1):
            listings.append({
                "seq_id": i,
                "sequence": d.sequence,
                "length": len(d.sequence),
                "design_id": d.design_id,
                "method": d.method,
                "plddt": d.plddt,
                "target": d.target
            })
        return listings
    
    def _format_patent(self, patent: PatentDraft) -> str:
        """Format patent as markdown"""
        parts = []
        parts.append(f"# {patent.title}")
        parts.append("")
        parts.append(f"**Inventors:** {', '.join(patent.inventors)}")
        parts.append("")
        parts.append(f"## Abstract\n{patent.abstract}")
        parts.append("")
        parts.append(f"## Description\n{patent.description}")
        parts.append("")
        parts.append("## Claims")
        for claim in patent.claims:
            parts.append(claim)
            parts.append("")
        parts.append("## Sequence Listing")
        for sl in patent.sequence_listings:
            parts.append(f"### SEQ ID NO: {sl['seq_id']}")
            parts.append(f"**Length:** {sl['length']} aa")
            parts.append(f"**Design ID:** {sl['design_id']}")
            parts.append(f"**Method:** {sl['method']}")
            parts.append(f"**pLDDT:** {sl['plddt']}")
            parts.append(f"**Target:** {sl['target']}")
            parts.append("")
            parts.append(f"```\n{sl['sequence']}\n```")
            parts.append("")
        return "\n".join(parts)
    
    def file_provisional(self, patent_id: str) -> Dict:
        """File provisional patent (placeholder - requires USPTO API or attorney)"""
        patent = self.patents.get(patent_id)
        if not patent:
            raise ValueError(f"Patent {patent_id} not found")
            
        # In production, this would integrate with USPTO EFS-Web or attorney
        patent.filed_date = datetime.now().isoformat()
        patent.application_number = f"63/{datetime.now().year}{len(self.patents):06d}"
        
        # Mark designs as patented
        for did in patent.design_ids:
            if did in self.designs:
                self.designs[did].patent_filed = True
                self.designs[did].patent_number = patent.application_number
                
        self._save_portfolio()
        
        logger.info(f"Provisional patent filed: {patent.application_number}")
        return {
            "status": "filed",
            "application_number": patent.application_number,
            "filed_date": patent.filed_date
        }
    
    def load_designs(self, file_path: str) -> List[Dict]:
        """Load designs from file"""
        with open(file_path) as f:
            return json.load(f)
    
    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary"""
        total_designs = len(self.designs)
        patented = sum(1 for d in self.designs.values() if d.patent_filed)
        total_patents = len(self.patents)
        
        # Estimate portfolio value
        avg_license_value = 500000  # Conservative
        estimated_value = patented * avg_license_value
        
        return {
            "total_designs": total_designs,
            "patented_designs": patented,
            "total_patents": total_patents,
            "estimated_value": estimated_value,
            "patents": list(self.patents.keys()),
            "designs_by_target": self._group_by_target()
        }
    
    def _group_by_target(self) -> Dict:
        """Group designs by target"""
        groups = {}
        for d in self.designs.values():
            if d.target not in groups:
                groups[d.target] = 0
            groups[d.target] += 1
        return groups
