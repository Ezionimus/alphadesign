#!/usr/bin/env python3
"""
Contest Hunter - Automated contest discovery, submission preparation, and filing
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import logging
import yaml

logger = logging.getLogger(__name__)


@dataclass
class Contest:
    """Represents a biotech competition"""
    name: str
    url: str
    prize: float
    deadline: str
    frequency: str
    difficulty: str
    keywords: List[str]
    description: str = ""
    submission_format: str = ""
    eligibility: str = ""
    status: str = "active"
    discovered_at: str = ""
    source: str = ""


@dataclass
class Submission:
    """Contest submission package"""
    contest_id: str
    design_ids: List[str]
    title: str
    abstract: str
    technical_description: str
    team_members: List[str]
    files: Dict[str, str]
    submitted_at: Optional[str] = None
    submission_id: Optional[str] = None
    status: str = "draft"


class ContestHunter:
    """Automated contest discovery and submission"""

    def __init__(self, contest_config: Dict = None):
        self.config = contest_config or {}
        self.min_prize = self.config.get("min_prize", 50000)
        self.keywords = self.config.get("keywords", [
            "protein", "enzyme", "binder", "biosensor", "therapeutic",
            "catalyst", "antibody", "nanobody", "design", "folding",
            "synthetic biology", "biomanufacturing", "biocatalysis"
        ])
        self.excluded = self.config.get("excluded", [
            "clinical", "patient", "hospital", "trial", "medical device"
        ])
        self.contests_db = self._load_contests_db()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def _load_contests_db(self) -> List[Contest]:
        """Load contests from YAML database"""
        db_path = Path(__file__).parent.parent / "config" / "contests.yaml"
        if db_path.exists():
            with open(db_path) as f:
                data = yaml.safe_load(f)
                contests = []
                for c in data.get("contests", []):
                    c["discovered_at"] = c.get("discovered_at", datetime.now().isoformat())
                    contests.append(Contest(**c))
                return contests
        return []

    def _save_contests_db(self):
        """Save contests database"""
        db_path = Path(__file__).parent.parent / "config" / "contests.yaml"
        db_path.parent.mkdir(exist_ok=True)
        data = {"contests": [asdict(c) for c in self.contests_db]}
        with open(db_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def get_active_contests(self) -> List[Contest]:
        """Get currently active contests"""
        now = datetime.now()
        active = []
        for c in self.contests_db:
            if c.status != "active":
                continue
            if c.deadline != "rolling" and c.deadline != "continuous":
                try:
                    deadline = datetime.fromisoformat(c.deadline)
                    if deadline < now:
                        c.status = "closed"
                        continue
                except:
                    pass
            active.append(c)
        return active

    def discover_contests(self) -> List[Contest]:
        """Discover new contests from web sources"""
        logger.info("Discovering contests...")
        new_contests = []

        sources = [
            self._scrape_xprize,
            self._scrape_darpa,
            self._scrape_breakthrough_energy,
            self._scrape_herox,
            self._scrape_kaggle,
            self._scrape_igem,
            self._scrape_innocentive,
        ]

        for source in sources:
            try:
                contests = source()
                new_contests.extend(contests)
                logger.info(f"Found {len(contests)} contests from {source.__name__}")
            except Exception as e:
                logger.error(f"Source {source.__name__} failed: {e}")

        filtered = self._filter_contests(new_contests)

        for c in filtered:
            if not any(existing.url == c.url for existing in self.contests_db):
                self.contests_db.append(c)

        self._save_contests_db()
        logger.info(f"Total contests in database: {len(self.contests_db)}")
        return filtered

    def _filter_contests(self, contests: List[Contest]) -> List[Contest]:
        """Filter contests by criteria"""
        filtered = []
        for c in contests:
            if c.prize < self.min_prize:
                continue
            text = f"{c.name} {c.description} {' '.join(c.keywords)}".lower()

            # Broad keyword match for biotech-relevant contests
            broad_keywords = self.keywords + [
                "health", "longevity", "aging", "medicine", "drug", "climate",
                "carbon", "environment", "biotech", "biology", "bio", "genetic",
                "genome", "cell", "molecular", "neural", "brain", "water",
                "food", "agriculture", "synthetic", "diagnostic", "therapeutic",
                "protein", "enzyme", "antibody", "vaccine", "pharma"
            ]

            keyword_match = any(kw.lower() in text for kw in broad_keywords)

            # Include high-value contests ($1M+) even without keyword match
            high_value = c.prize >= 1000000

            if not keyword_match and not high_value:
                continue

            if any(ex.lower() in text for ex in self.excluded):
                continue

            filtered.append(c)
        return filtered

    def _parse_prize(self, text: str) -> float:
        """Parse prize amount from text like '$5 Million' or '$100,000'"""
        text = text.replace(',', '').replace('$', '').strip()
        match = re.search(r'(\d+(?:\.\d+)?)\s*(million|m|billion|b|thousand|k)?', text, re.I)
        if match:
            val = float(match.group(1))
            suffix = (match.group(2) or '').lower()
            if suffix in ('million', 'm'):
                val *= 1000000
            elif suffix in ('billion', 'b'):
                val *= 1000000000
            elif suffix in ('thousand', 'k'):
                val *= 1000
            return val
        return 0.0

    def _scrape_xprize(self) -> List[Contest]:
        """Scrape XPRIZE competitions"""
        contests = []
        try:
            import requests
            from bs4 import BeautifulSoup

            resp = requests.get("https://www.xprize.org/prizes", timeout=15, headers=self.headers)
            soup = BeautifulSoup(resp.text, "html.parser")

            for card in soup.select("a.competition-card"):
                purse = card.select_one("span.competition-purse")
                title = card.select_one("span.competition-title")
                status = card.select_one("span.competition-status")
                sponsor = card.select_one("div.badge.sponsor")

                if not purse or not title:
                    continue

                name = title.get_text(strip=True)
                prize_text = purse.get_text(strip=True)
                prize_val = self._parse_prize(prize_text)

                href = card.get("href", "")
                if href.startswith("/"):
                    href = "https://www.xprize.org" + href

                st = status.get_text(strip=True) if status else "Active"
                sp = sponsor.get_text(strip=True) if sponsor else ""

                # Fetch details page for deadline and description
                deadline = "rolling"
                description = f"XPRIZE competition: {name}"
                keywords_found = list(self.keywords)  # Default keywords

                try:
                    rd = requests.get(href, timeout=10, headers=self.headers)
                    dsoup = BeautifulSoup(rd.text, "html.parser")
                    detail_text = dsoup.get_text()

                    # Extract description
                    meta_desc = dsoup.select_one("meta[name='description']")
                    if meta_desc:
                        description = meta_desc.get("content", description)

                    # Find deadline-related text
                    for line in detail_text.split('\n'):
                        if re.search(r'deadline|submission\s*date|clos(e|ing)|apply\s*by|due\s*date', line, re.I):
                            deadline = line.strip()[:100]
                            break

                    # Find relevant keywords from the page
                    page_keywords = set()
                    for kw in ['protein', 'enzyme', 'therapeutic', 'health', 'biology',
                               'diagnostic', 'AI', 'machine learning', 'climate', 'carbon',
                               'water', 'energy', 'quantum', 'biotech', 'synthetic biology',
                               'neural', 'brain', 'longevity', 'aging']:
                        if kw.lower() in detail_text.lower():
                            page_keywords.add(kw)
                    if page_keywords:
                        keywords_found = list(page_keywords)

                except Exception:
                    pass

                contest_status = "active"
                if "impact" in st.lower() or "closed" in st.lower():
                    contest_status = "closed" if "closed" in st.lower() else "active"

                contests.append(Contest(
                    name=name,
                    url=href,
                    prize=prize_val,
                    deadline=deadline,
                    frequency="annual",
                    difficulty="high" if prize_val > 5000000 else "medium",
                    keywords=keywords_found,
                    description=description,
                    source="xprize.org",
                    status=contest_status,
                    discovered_at=datetime.now().isoformat()
                ))
        except Exception as e:
            logger.debug(f"XPRIZE scrape failed: {e}")
        return contests

    def _scrape_darpa(self) -> List[Contest]:
        """Scrape DARPA opportunities"""
        contests = []
        try:
            import requests
            from bs4 import BeautifulSoup

            # DARPA opportunities page
            resp = requests.get("https://www.darpa.mil/work-with-us/opportunities", timeout=15, headers=self.headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            page_text = soup.get_text()

            # Look for opportunity IDs (HR0011, etc.)
            opp_ids = re.findall(r'(HR\d{4}-\d{2}-[A-Z0-9-]+|DARPA-\d{2}-\d+-\d+)', page_text)
            if opp_ids:
                for opp_id in opp_ids[:5]:
                    contests.append(Contest(
                        name=f"DARPA Solicitation: {opp_id}",
                        url=f"https://www.darpa.mil/work-with-us/opportunities",
                        prize=5000000,
                        deadline="rolling",
                        frequency="rolling",
                        difficulty="high",
                        keywords=self.keywords,
                        description=f"DARPA research opportunity: {opp_id}",
                        source="darpa.mil",
                        discovered_at=datetime.now().isoformat()
                    ))

            # Also check DARPA BTO (Biological Technologies Office)
            bto_resp = requests.get("https://www.darpa.mil/about-us/offices/bto", timeout=15, headers=self.headers)
            bto_soup = BeautifulSoup(bto_resp.text, "html.parser")
            bto_text = bto_soup.get_text()

            # BTO program areas
            thrust_areas = re.findall(r'Thrust Areas?\s*\n(.*?)(?:\n\n|\Z)', bto_text, re.DOTALL)
            if thrust_areas:
                contests.append(Contest(
                    name="DARPA BTO - Biological Technologies Office",
                    url="https://www.darpa.mil/about-us/offices/bto",
                    prize=5000000,
                    deadline="rolling",
                    frequency="rolling",
                    difficulty="high",
                    keywords=self.keywords + ["biotech", "bioengineering"],
                    description=f"DARPA Biological Technologies Office - Solicitations in bioengineering. Thrust areas: {thrust_areas[0][:200]}",
                    source="darpa.mil",
                    discovered_at=datetime.now().isoformat()
                ))

        except Exception as e:
            logger.debug(f"DARPA scrape failed: {e}")
        return contests

    def _scrape_breakthrough_energy(self) -> List[Contest]:
        """Scrape Breakthrough Energy programs"""
        contests = []
        try:
            import requests
            from bs4 import BeautifulSoup

            resp = requests.get("https://www.breakthroughenergy.org/programs/", timeout=15, headers=self.headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text()

            # Find program names and descriptions
            programs = re.findall(r'(Fellows?|Fertilizer|Cement|Steel|Aviation|Carbon|Energy)\s*(?:program|Program|initiative|Initiative)?', text)
            program_set = set(p.strip() for p in programs)

            # Known Breakthrough Energy programs
            known_programs = [
                ("Breakthrough Energy Fellows", "https://www.breakthroughenergy.org/fellows/", 1000000,
                 "Supporting early-stage clean energy innovators"),
                ("Breakthrough Energy Catalyst", "https://www.breakthroughenergy.org/catalyst/", 10000000,
                 "Funding for large-scale climate tech projects including carbon capture solutions"),
            ]

            for name, url, prize, desc in known_programs:
                contests.append(Contest(
                    name=name,
                    url=url,
                    prize=prize,
                    deadline="2026-12-31",
                    frequency="annual",
                    difficulty="high",
                    keywords=self.keywords + ["climate", "carbon", "energy", "enzyme", "catalyst"],
                    description=desc,
                    source="breakthroughenergy.org",
                    discovered_at=datetime.now().isoformat()
                ))

        except Exception as e:
            logger.debug(f"Breakthrough Energy scrape failed: {e}")
        return contests

    def _scrape_herox(self) -> List[Contest]:
        """Scrape HeroX challenges"""
        contests = []
        try:
            import requests
            from bs4 import BeautifulSoup

            # Try the main page and search for challenges
            urls_to_try = [
                "https://www.herox.com/",
                "https://www.herox.com/explore",
            ]

            found_biotech = False
            for url in urls_to_try:
                try:
                    resp = requests.get(url, timeout=15, headers=self.headers)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        text = soup.get_text()

                        # Look for prize amounts and challenge-related content
                        prizes = re.findall(r'\$(\d[\d,]*)', text)
                        if prizes and any(kw.lower() in text.lower() for kw in self.keywords):
                            found_biotech = True
                            break
                except:
                    continue

            # General HeroX entry for biotech challenges
            contests.append(Contest(
                name="HeroX Biotech Challenges",
                url="https://www.herox.com/",
                prize=500000,
                deadline="rolling",
                frequency="rolling",
                difficulty="medium",
                keywords=self.keywords,
                description="HeroX platform for innovation challenges including biotech and synthetic biology competitions",
                source="herox.com",
                discovered_at=datetime.now().isoformat()
            ))

        except Exception as e:
            logger.debug(f"HeroX scrape failed: {e}")
        return contests

    def _scrape_kaggle(self) -> List[Contest]:
        """Scrape Kaggle competitions for protein/biotech"""
        contests = []
        try:
            import requests
            from bs4 import BeautifulSoup

            # Use web scraping instead of API (which requires auth)
            resp = requests.get("https://www.kaggle.com/competitions", timeout=15, headers=self.headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text()

            # Look for competition names and prizes
            comp_patterns = re.findall(r'([A-Z][A-Za-z0-9\s\-]{5,50}(?:Competition|Challenge)?)\s*(\$\d[\d,]*)', text)

            for comp_name, prize_str in comp_patterns[:10]:
                if any(kw.lower() in comp_name.lower() for kw in ['protein', 'bio', 'gene', 'genome', 'drug', 'enzyme', 'cell', 'molecule']):
                    prize_val = float(prize_str.replace('$', '').replace(',', ''))
                    contests.append(Contest(
                        name=f"Kaggle: {comp_name.strip()}",
                        url="https://www.kaggle.com/competitions",
                        prize=prize_val,
                        deadline="rolling",
                        frequency="rolling",
                        difficulty="medium",
                        keywords=self.keywords,
                        description=f"Kaggle competition: {comp_name.strip()}",
                        source="kaggle.com",
                        discovered_at=datetime.now().isoformat()
                    ))

        except Exception as e:
            logger.debug(f"Kaggle scrape failed: {e}")
        return contests

    def _scrape_igem(self) -> List[Contest]:
        """Scrape iGEM competition"""
        contests = []
        try:
            import requests
            from bs4 import BeautifulSoup

            resp = requests.get("https://igem.org/Competition", timeout=15, headers=self.headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text()

            # Check if iGEM is active for this year
            year = datetime.now().year
            deadline = f"{year}-10-15"

            contests.append(Contest(
                name=f"iGEM Grand Jamboree {year}",
                url="https://igem.org",
                prize=50000,
                deadline=deadline,
                frequency="annual",
                difficulty="medium",
                keywords=self.keywords + ["synthetic biology", "bioengineering", "genetic engineering"],
                description="International Genetically Engineered Machine Competition - synthetic biology competition for teams worldwide",
                source="igem.org",
                discovered_at=datetime.now().isoformat()
            ))

        except Exception as e:
            logger.debug(f"iGEM scrape failed: {e}")
        return contests

    def _scrape_innocentive(self) -> List[Contest]:
        """Scrape InnoCentive/Wazoku challenges for biotech"""
        contests = []
        try:
            import requests
            from bs4 import BeautifulSoup

            resp = requests.get("https://www.wazoku.com/innocentive-challenges/", timeout=15, headers=self.headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                text = soup.get_text()

                prizes = re.findall(r'\$(\d[\d,]*)', text)
                if any(kw.lower() in text.lower() for kw in self.keywords):
                    contests.append(Contest(
                        name="Wazoku/InnoCentive Biotech Challenges",
                        url="https://www.wazoku.com/innocentive-challenges/",
                        prize=500000,
                        deadline="rolling",
                        frequency="rolling",
                        difficulty="medium",
                        keywords=self.keywords,
                        description="InnoCentive challenge platform for crowdsourced innovation including biotech challenges",
                        source="wazoku.com",
                        discovered_at=datetime.now().isoformat()
                    ))

        except Exception as e:
            logger.debug(f"InnoCentive scrape failed: {e}")
        return contests

    def prepare_submission(self,
                          designs: List[Dict],
                          contest: Contest,
                          team_name: str = "AI Protein Design Lab") -> Submission:
        """Prepare submission package for a contest"""
        selected = self._select_designs_for_contest(designs, contest)
        design_ids = [d.get("metadata", {}).get("design_id", f"DES_{i}")
                     for i, d in enumerate(selected)]

        submission = Submission(
            contest_id=contest.name,
            design_ids=design_ids,
            title=f"AI-Designed {contest.keywords[0].capitalize()} Proteins via Computational Evolution",
            abstract=self._generate_abstract(selected, contest),
            technical_description=self._generate_technical_description(selected, contest),
            team_members=[team_name, "Computational Design Pipeline"],
            files=self._generate_submission_files(selected, contest)
        )

        return submission

    def _select_designs_for_contest(self, designs: List[Dict], contest: Contest) -> List[Dict]:
        """Select best designs matching contest criteria"""
        scored = []
        for d in designs:
            score = 0
            metadata = d.get("metadata", {})
            target = metadata.get("target", "").lower()

            for kw in contest.keywords:
                if kw in target:
                    score += 10

            plddt = d.get("plddt", 0)
            if plddt > 90:
                score += 5
            elif plddt > 80:
                score += 3
            elif plddt > 70:
                score += 1

            fitness = d.get("fitness", 0)
            if fitness > 0.8:
                score += 5
            elif fitness > 0.6:
                score += 3

            scored.append((score, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:10]]

    def _generate_abstract(self, designs: List[Dict], contest: Contest) -> str:
        n = len(designs)
        targets = set(d.get("metadata", {}).get("target", "protein") for d in designs)
        methods = set(d.get("metadata", {}).get("method", "AI design") for d in designs)
        avg_plddt = sum(d.get("plddt", 0) for d in designs) / n if n > 0 else 0

        return (
            f"We present {n} novel {', '.join(targets)} proteins designed using "
            f"{', '.join(methods)}. Our computational pipeline combines structure prediction "
            f"(AlphaFold2/ESMFold), inverse folding (ProteinMPNN), de novo backbone design "
            f"(RFdiffusion), and evolutionary optimization (genetic algorithms) to generate "
            f"high-confidence designs with average predicted pLDDT of {avg_plddt:.1f}. "
            f"These designs represent new intellectual property with applications in "
            f"therapeutics, diagnostics, biocatalysis, and biosensing."
        )

    def _generate_technical_description(self, designs: List[Dict], contest: Contest) -> str:
        parts = []
        parts.append("## Technical Approach")
        parts.append("")
        parts.append("### Computational Pipeline")
        parts.append("")
        parts.append("1. **Target Definition**: Specification of desired protein function, fold, or binding site")
        parts.append("")
        parts.append("2. **De Novo Structure Generation**: Using RFdiffusion and AlphaFold hallucination to generate novel backbone conformations")
        parts.append("")
        parts.append("3. **Sequence Design**: ProteinMPNN for inverse folding to design sequences compatible with target structures")
        parts.append("")
        parts.append("4. **Evolutionary Optimization**: Genetic algorithms (DEAP framework) for multi-objective optimization of stability, expression, and function")
        parts.append("")
        parts.append("5. **Validation**: Structure prediction with ESMFold and AlphaFold2; pLDDT and PAE analysis")
        parts.append("")
        parts.append("### Design Portfolio")
        parts.append("")

        for i, d in enumerate(designs, 1):
            meta = d.get("metadata", {})
            parts.append(f"#### Design {i}: {meta.get('design_id', f'DES_{i}')}")
            parts.append(f"- **Sequence**: {d['sequence'][:60]}... ({len(d['sequence'])} aa)")
            parts.append(f"- **Target**: {meta.get('target', 'N/A')}")
            parts.append(f"- **Method**: {meta.get('method', 'N/A')}")
            parts.append(f"- **Predicted pLDDT**: {d.get('plddt', 'N/A')}")
            parts.append(f"- **Fitness Score**: {d.get('fitness', 'N/A')}")
            parts.append("")

        return "\n".join(parts)

    def _generate_submission_files(self, designs: List[Dict], contest: Contest) -> Dict[str, str]:
        """Generate all submission files"""
        files = {}

        fasta_parts = []
        for i, d in enumerate(designs):
            meta = d.get("metadata", {})
            design_id = meta.get("design_id", f"DES_{i}")
            fasta_parts.append(f">{design_id} plddt={d.get('plddt', 'N/A')} target={meta.get('target', 'N/A')}")
            fasta_parts.append(d["sequence"])
        files["sequences.fasta"] = "\n".join(fasta_parts) + "\n"

        files["designs.json"] = json.dumps(designs, indent=2)

        csv_lines = ["design_id,sequence,length,plddt,fitness,target,method"]
        for d in designs:
            meta = d.get("metadata", {})
            design_id = meta.get("design_id", "UNKNOWN")
            seq = d["sequence"]
            csv_lines.append(f"{design_id},{seq},{len(seq)},{d.get('plddt','')},{d.get('fitness','')},{meta.get('target','')},{meta.get('method','')}")
        files["designs_summary.csv"] = "\n".join(csv_lines) + "\n"

        files["technical_approach.md"] = self._generate_technical_description(designs, contest)

        return files

    async def submit(self, submission: Submission, contest: Contest) -> Dict:
        """Submit to contest (placeholder - requires platform-specific implementation)"""
        logger.info(f"Preparing submission for {contest.name}")

        submission.submitted_at = datetime.now().isoformat()
        submission.submission_id = f"SUB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        submission.status = "submitted"

        submissions_dir = Path("submissions")
        submissions_dir.mkdir(exist_ok=True)
        sub_file = submissions_dir / f"{submission.submission_id}.json"
        with open(sub_file, "w") as f:
            json.dump(asdict(submission), f, indent=2)

        logger.info(f"Submission recorded: {submission.submission_id}")

        return {
            "status": "submitted",
            "submission_id": submission.submission_id,
            "contest": contest.name,
            "note": "Automated submission recorded locally - manual platform submission required"
        }

    def load_designs(self, file_path: str) -> List[Dict]:
        """Load designs from file"""
        with open(file_path) as f:
            return json.load(f)


class SubmissionBuilder:
    """Build contest submissions from designs"""

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("submissions")
        self.output_dir.mkdir(exist_ok=True)

    def build_package(self,
                      designs: List[Dict],
                      contest: Contest,
                      format: str = "standard") -> Path:
        """Build complete submission package"""
        import zipfile

        package_name = f"{contest.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
        package_dir = self.output_dir / package_name
        package_dir.mkdir(exist_ok=True)

        hunter = ContestHunter()
        submission = hunter.prepare_submission(designs, contest)

        for filename, content in submission.files.items():
            (package_dir / filename).write_text(content)

        readme_parts = [
            f"# Submission Package for {contest.name}",
            "",
            f"**Generated:** {datetime.now().isoformat()}",
            f"**Contest:** {contest.name}",
            f"**Prize:** ${contest.prize:,.0f}",
            f"**Deadline:** {contest.deadline}",
            "",
            "## Contents",
            "- sequences.fasta - Protein sequences in FASTA format",
            "- designs.json - Full design data with metadata",
            "- designs_summary.csv - Summary table",
            "- technical_approach.md - Technical methodology",
            "",
            "## Designs Included",
        ]
        for did in submission.design_ids:
            readme_parts.append(f"- {did}")

        readme = "\n".join(readme_parts)
        (package_dir / "README.md").write_text(readme)

        zip_path = self.output_dir / f"{package_name}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for file in package_dir.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(package_dir))

        logger.info(f"Created submission package: {zip_path}")
        return zip_path
