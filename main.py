#!/usr/bin/env python3
"""
Protein Contest Automation - MAIN ENTRY POINT
Lethal zero-capital biotech IP generation system

Usage:
    python -m protein_contest_automation design --target denovo --num 100
    python -m protein_contest_automation hunt --discover
    python -m protein_contest_automation pipeline --cycles 1
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add skill directory to path
sys.path.insert(0, str(Path(__file__).parent))

from designer.protein_designer import ProteinDesigner
from hunter.contest_hunter import ContestHunter, SubmissionBuilder
from ip.ip_agent import IPAgent
from licensing.licensing_framework import LicensingManager, PortfolioValuation
from utils.utilities import GPUManager, BatchProcessor, StructuredLogger, CheckpointManager


class ProteinContestPipeline:
    """Orchestrates the full pipeline: Design -> Hunt -> IP -> License"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.gpu_manager = GPUManager()
        self.logger = StructuredLogger("pipeline")
        self.checkpoint = CheckpointManager()
        
        # Initialize components
        self.designer = ProteinDesigner(self.config.get("gpu", {}))
        self.hunter = ContestHunter(self.config.get("contests", {}))
        self.ip_agent = IPAgent(self.config.get("ip", {}))
        self.licensing = LicensingManager(Path(self.config.get("ip", {}).get("portfolio_path", "ip_portfolio")))
        
        # Stats
        self.stats = {
            "designs_created": 0,
            "contests_entered": 0,
            "patents_filed": 0,
            "licenses_created": 0
        }
        
    async def run_design_phase(self, num_designs: int = 200) -> list:
        """Phase 1: Design novel proteins"""
        self.logger.log_pipeline("design", "started", {"target": num_designs})
        
        # De novo design
        designs = self.designer.design_de_novo(
            target_fold=self.config.get("design", {}).get("target_fold", "TIM_barrel"),
            constraints=self.config.get("design", {}).get("constraints", {}),
            num_designs=num_designs
        )
        
        # Evolutionary optimization
        if self.config.get("evolution", {}).get("enabled", True) and designs:
            sequences = [d.sequence for d in designs if d.sequence]
            if sequences:
                evolved = self.designer.evolve_sequences(
                    sequences,
                    generations=self.config.get("evolution", {}).get("generations", 30),
                    population=self.config.get("evolution", {}).get("population", 100)
                )
                # Combine originals with evolved designs
                designs = evolved + designs[:max(10, num_designs//4)]
            
        self.stats["designs_created"] = len(designs)
        self.logger.log_pipeline("design", "completed", {"count": len(designs)})
        
        # Save checkpoint
        self.checkpoint.save("design", {"designs": [d.__dict__ for d in designs]})
        
        return designs
    
    async def run_ip_phase(self, designs: list) -> list:
        """Phase 2: IP protection"""
        self.logger.log_pipeline("ip", "started", {"designs": len(designs)})

        # Convert ProteinDesign objects to dicts for IP agent
        design_dicts = []
        for d in designs:
            if hasattr(d, '__dict__'):
                dd = d.__dict__.copy()
                # Convert metadata to dict
                if hasattr(d, 'metadata') and d.metadata:
                    dd['metadata'] = dict(d.metadata)
                else:
                    dd['metadata'] = {}
                design_dicts.append(dd)
            else:
                design_dicts.append(d)

        # Track designs
        design_ids = self.ip_agent.track_designs(design_dicts)
        
        # Generate provisional patents
        patents = []
        batch_size = self.config.get("ip", {}).get("patent_batch_size", 20)
        
        for i in range(0, len(design_ids), batch_size):
            batch = design_ids[i:i+batch_size]
            patent = self.ip_agent.generate_provisional_patent(batch)
            patents.append(patent)
            
            # Auto-file if configured
            if self.config.get("ip", {}).get("auto_file", False):
                self.ip_agent.file_provisional(patent)
                self.stats["patents_filed"] += 1
                
        self.logger.log_pipeline("ip", "completed", {"patents": len(patents)})
        return patents
    
    async def run_hunt_phase(self, designs: list) -> list:
        """Phase 3: Contest hunting and submission"""
        self.logger.log_pipeline("hunt", "started")
        
        # Discover contests
        contests = self.hunter.discover_contests()
        
        # Get active contests
        active = self.hunter.get_active_contests()
        
        # Submit to top contests
        submissions = []
        max_contests = self.config.get("pipeline", {}).get("max_contests_per_cycle", 10)
        
        for contest in active[:max_contests]:
            try:
                # Convert ProteinDesign objects to dicts for submission builder
                design_dicts = []
                for d in designs:
                    if hasattr(d, '__dict__'):
                        dd = d.__dict__.copy()
                        if hasattr(d, 'metadata') and d.metadata:
                            dd['metadata'] = dict(d.metadata)
                        else:
                            dd['metadata'] = {}
                        design_dicts.append(dd)
                    else:
                        design_dicts.append(d)
                submission = self.hunter.prepare_submission(design_dicts, contest)
                result = await self.hunter.submit(submission, contest)
                submissions.append(result)
                self.stats["contests_entered"] += 1
                self.logger.log_contest(contest.name, "submitted", {"designs": len(submission.design_ids)})
            except Exception as e:
                self.logger.log_contest(contest.name, "failed", {"error": str(e)})
                
        self.logger.log_pipeline("hunt", "completed", {"submissions": len(submissions)})
        return submissions
    
    async def run_licensing_phase(self) -> list:
        """Phase 4: License portfolio"""
        self.logger.log_pipeline("license", "started")
        
        # Get patented designs
        portfolio = self.ip_agent.get_portfolio_summary()
        
        # Valuation
        valuation = PortfolioValuation()
        
        # This would create license agreements when there's interest
        # For now, just report portfolio value
        self.logger.log_pipeline("license", "completed", portfolio)
        return [portfolio]
    
    async def run_full_cycle(self) -> dict:
        """Run complete pipeline cycle"""
        self.logger.log_pipeline("full_cycle", "started")
        
        # Phase 1: Design
        designs = await self.run_design_phase(
            self.config.get("pipeline", {}).get("design_batch_size", 200)
        )
        
        # Phase 2: IP
        patents = await self.run_ip_phase(designs)
        
        # Phase 3: Hunt
        submissions = await self.run_hunt_phase(designs)
        
        # Phase 4: License
        portfolio = await self.run_licensing_phase()
        
        # Save designs
        self.designer.save_designs(designs, Path("outputs/designs"))
        
        self.logger.log_pipeline("full_cycle", "completed", self.stats)
        
        return {
            "designs": len(designs),
            "patents": len(patents),
            "submissions": len(submissions),
            "portfolio": portfolio[0] if portfolio else {},
            "stats": self.stats
        }


def design_command(args, config):
    """Design proteins command"""
    pipeline = ProteinContestPipeline(config)
    
    if args.target == "denovo":
        designs = asyncio.run(pipeline.designer.design_de_novo(
            target_fold=args.fold,
            constraints=json.loads(args.constraints) if args.constraints else {},
            num_designs=args.num
        ))
    elif args.target == "binder":
        designs = asyncio.run(pipeline.designer.design_binder(
            target_pdb=args.target_pdb,
            binding_site=args.site,
            num_designs=args.num
        ))
    elif args.target == "optimize":
        # Load sequences from file
        with open(args.sequences) as f:
            sequences = json.load(f)
        designs = asyncio.run(pipeline.designer.evolve_sequences(
            sequences,
            generations=args.generations,
            population=args.population
        ))
        
    pipeline.designer.save_designs(designs, Path(args.output))
    print(f"Created {len(designs)} designs in {args.output}")


def hunt_command(args, config):
    """Contest hunting command"""
    hunter = ContestHunter(config.get("contests", {}))
    
    if args.discover:
        contests = hunter.discover_contests()
        print(f"Discovered {len(contests)} new contests:")
        for c in contests:
            print(f"  {c.name}: ${c.prize:,.0f} - {c.deadline} - {c.url}")
            
    if args.submit:
        designs = hunter.load_designs(args.designs_file)
        contests = hunter.get_active_contests()
        
        for contest in contests[:args.max_contests]:
            submission = hunter.prepare_submission(designs, contest)
            result = asyncio.run(hunter.submit(submission, contest))
            print(f"Submitted to {contest.name}: {result['status']}")


def ip_command(args, config):
    """IP management command"""
    ip = IPAgent(config.get("ip", {}))
    
    if args.track:
        designs = ip.load_designs(args.designs_file)
        ids = ip.track_designs(designs)
        print(f"Tracked {len(ids)} designs")
        
    if args.patent:
        designs = ip.load_designs(args.designs_file)
        ids = ip.track_designs(designs)
        patents = []
        batch_size = 20
        for i in range(0, len(ids), batch_size):
            patent = ip.generate_provisional_patent(ids[i:i+batch_size])
            patents.append(patent)
            print(f"Generated patent: {patent}")
            
        if args.file:
            for patent in patents:
                result = ip.file_provisional(patent)
                print(f"Filed: {result}")


def pipeline_command(args, config):
    """Run full pipeline"""
    pipeline = ProteinContestPipeline(config)

    for cycle in range(args.cycles):
        print("\n" + "="*50)
        print(f"CYCLE {cycle+1}/{args.cycles}")
        print("="*50)

        result = asyncio.run(pipeline.run_full_cycle())

        print("Results:")
        print(f"  Designs: {result['designs']}")
        print(f"  Patents: {result['patents']}")
        print(f"  Submissions: {result['submissions']}")
        print(f"  Portfolio Value: ${result['portfolio'].get('estimated_value', 0):,.0f}")


def load_config(config_path: str = None) -> dict:
    """Load configuration"""
    import yaml
    
    config = {}
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
            
    # Default config
    default = {
        "gpu": {"device_id": 0, "memory_fraction": 0.9},
        "design": {"target_fold": "TIM_barrel", "constraints": {}},
        "evolution": {"enabled": True, "generations": 30, "population": 100},
        "contests": {"min_prize": 50000},
        "ip": {"auto_file": False, "portfolio_path": "ip_portfolio", "patent_batch_size": 20},
        "pipeline": {"design_batch_size": 200, "max_contests_per_cycle": 10}
    }
    
    # Merge configs
    def merge(d1, d2):
        for k, v in d2.items():
            if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
                merge(d1[k], v)
            else:
                d1[k] = v
                
    merge(default, config)
    return default


def main():
    parser = argparse.ArgumentParser(description="Protein Contest Automation")
    parser.add_argument("--config", help="Config file path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Design command
    design_parser = subparsers.add_parser("design", help="Design proteins")
    design_parser.add_argument("target", choices=["denovo", "binder", "optimize"])
    design_parser.add_argument("--fold", help="Target fold for denovo")
    design_parser.add_argument("--constraints", help="JSON constraints")
    design_parser.add_argument("--target-pdb", help="Target PDB for binder")
    design_parser.add_argument("--site", help="Binding site")
    design_parser.add_argument("--sequences", help="Input sequences file")
    design_parser.add_argument("--generations", type=int, default=50)
    design_parser.add_argument("--population", type=int, default=100)
    design_parser.add_argument("--num", type=int, default=100)
    design_parser.add_argument("--output", default="outputs/designs")
    
    # Hunt command
    hunt_parser = subparsers.add_parser("hunt", help="Contest hunting")
    hunt_parser.add_argument("--discover", action="store_true")
    hunt_parser.add_argument("--submit", action="store_true")
    hunt_parser.add_argument("--designs-file", help="Designs JSON file")
    hunt_parser.add_argument("--max-contests", type=int, default=10)
    
    # IP command
    ip_parser = subparsers.add_parser("ip", help="IP management")
    ip_parser.add_argument("--track", action="store_true")
    ip_parser.add_argument("--patent", action="store_true")
    ip_parser.add_argument("--file", action="store_true")
    ip_parser.add_argument("--designs-file", help="Designs JSON file")
    
    # Pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="Run full pipeline")
    pipeline_parser.add_argument("--cycles", type=int, default=1)
    
    args = parser.parse_args()
    config = load_config(args.config)
    
    if args.command == "design":
        design_command(args, config)
    elif args.command == "hunt":
        hunt_command(args, config)
    elif args.command == "ip":
        ip_command(args, config)
    elif args.command == "pipeline":
        pipeline_command(args, config)


if __name__ == "__main__":
    main()
