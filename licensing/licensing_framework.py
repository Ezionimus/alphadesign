#!/usr/bin/env python3
"""
Licensing Framework - Royalty calculation, agreement templates, portfolio valuation
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class LicenseAgreement:
    """License agreement terms"""
    license_id: str
    patent_ids: List[str]
    licensee: str
    licensor: str
    license_type: str  # exclusive, non-exclusive, field-limited
    territory: List[str]
    field_of_use: List[str]
    royalty_rate: float  # percentage (e.g., 0.05 = 5%)
    minimum_annual_royalty: float
    upfront_fee: float
    milestone_payments: Dict[str, float]
    start_date: str
    end_date: Optional[str]
    status: str  # draft, active, expired, terminated


@dataclass
class Milestone:
    """Commercial milestone"""
    name: str
    description: str
    trigger: str
    payment: float
    due_date: Optional[str]
    status: str  # pending, achieved, paid


class RoyaltyCalculator:
    """Calculate royalties and NPV of license deals"""
    
    def __init__(self, discount_rate: float = 0.15):
        self.discount_rate = discount_rate
        
    def calculate_npv(self, 
                      upfront: float,
                      annual_royalties: List[float],
                      milestones: List[Dict],
                      years: int = 20) -> Dict:
        """Calculate NPV of license deal"""
        npv = upfront
        
        # Discount annual royalties
        for year, royalty in enumerate(annual_royalties, 1):
            if year > years:
                break
            npv += royalty / (1 + self.discount_rate) ** year
            
        # Discount milestones
        for m in milestones:
            if m.get("year", 0) > 0 and m.get("year", 0) <= years:
                npv += m["payment"] / (1 + self.discount_rate) ** m["year"]
                
        return {
            "npv": npv,
            "upfront": upfront,
            "royalty_pv": sum(r / (1 + self.discount_rate) ** (i+1) 
                            for i, r in enumerate(annual_royalties[:years])),
            "milestone_pv": sum(m["payment"] / (1 + self.discount_rate) ** m["year"] 
                              for m in milestones if m.get("year", 0) <= years),
            "discount_rate": self.discount_rate,
            "years": years
        }
    
    def project_royalties(self,
                          peak_sales: float,
                          ramp_years: int = 5,
                          decay_years: int = 10,
                          royalty_rate: float = 0.05,
                          market_share: float = 0.1) -> List[float]:
        """Project annual royalties based on market assumptions"""
        royalties = []
        for year in range(1, 21):
            if year <= ramp_years:
                # Ramp up
                sales = peak_sales * (year / ramp_years) * market_share
            elif year <= ramp_years + decay_years:
                # Plateau then decay
                decay_year = year - ramp_years
                sales = peak_sales * market_share * (1 - decay_year / decay_years * 0.5)
            else:
                # Long tail
                sales = peak_sales * market_share * 0.3
                
            royalties.append(sales * royalty_rate)
            
        return royalties


class AgreementTemplates:
    """License agreement templates"""
    
    @staticmethod
    def exclusive_license(patent_ids: List[str], licensee: str, terms: Dict) -> str:
        """Generate exclusive license agreement"""
        return f"""
EXCLUSIVE LICENSE AGREEMENT

This Exclusive License Agreement ("Agreement") is entered into as of {datetime.now().strftime('%B %d, %Y')} 
by and between:

LICENSOR: [Inventor/Assignee Name]
LICENSEE: {licensee}

WHEREAS, Licensor owns rights to the following patent applications/patents:
{chr(10).join(f'  - {pid}' for pid in patent_ids)}

WHEREAS, Licensee desires to obtain an exclusive license to practice the Licensed Patents 
in the Field of Use and Territory defined below;

NOW, THEREFORE, the parties agree as follows:

1. GRANT OF LICENSE
   Licensor grants to Licensee an exclusive, worldwide license under the Licensed Patents 
   to make, have made, use, sell, offer for sale, and import Licensed Products in the 
   Field of Use: {', '.join(terms.get('field_of_use', ['therapeutics', 'diagnostics', 'industrial enzymes']))}.

2. TERRITORY
   {', '.join(terms.get('territory', ['Worldwide']))}

3. FINANCIAL TERMS
   3.1 Upfront Fee: ${terms.get('upfront_fee', 50000):,.2f}
   3.2 Running Royalty: {terms.get('royalty_rate', 0.05)*100:.1f}% of Net Sales
   3.3 Minimum Annual Royalty: ${terms.get('minimum_annual', 25000):,.2f} (Year 2+)
   
   Milestone Payments:
{chr(10).join(f'     - {k}: ${v:,.2f}' for k, v in terms.get('milestones', {}).items())}

4. DILIGENCE
   Licensee shall use commercially reasonable efforts to develop and commercialize 
   Licensed Products. Key milestones:
{chr(10).join(f'     - {k}: by {v}' for k, v in terms.get('diligence_milestones', {}).items())}

5. TERM AND TERMINATION
   Term: {terms.get('term_years', 20)} years from Effective Date
   Termination for material breach with 90-day cure period.

6. PATENT PROSECUTION
   Licensor controls prosecution; Licensee reimburses costs.

7. INFRINGEMENT
   Licensee has first right to enforce; Licensor joins if requested.

IN WITNESS WHEREOF, the parties have executed this Agreement.

LICENSOR: _________________________ DATE: ___________
LICENSEE: _________________________ DATE: ___________
"""
    
    @staticmethod
    def non_exclusive_license(patent_ids: List[str], licensee: str, terms: Dict) -> str:
        """Generate non-exclusive license agreement"""
        return f"""
NON-EXCLUSIVE LICENSE AGREEMENT

Licensor: [Inventor/Assignee]
Licensee: {licensee}
Patents: {', '.join(patent_ids)}
Field: {', '.join(terms.get('field_of_use', ['research tools']))}
Territory: {', '.join(terms.get('territory', ['Worldwide']))}
Royalty: {terms.get('royalty_rate', 0.03)*100:.1f}%
Upfront: ${terms.get('upfront_fee', 10000):,.2f}
Term: {terms.get('term_years', 10)} years

[Standard non-exclusive terms...]
"""
    
    @staticmethod
    def option_agreement(patent_ids: List[str], optionee: str, terms: Dict) -> str:
        """Generate option to license agreement"""
        return f"""
OPTION TO LICENSE AGREEMENT

Optionor: [Inventor/Assignee]
Optionee: {optionee}
Option Period: {terms.get('option_period_months', 12)} months
Option Fee: ${terms.get('option_fee', 5000):,.2f}
Exercise Terms: Convert to {terms.get('license_type', 'exclusive')} license on terms 
to be negotiated in good faith.

Patents Subject to Option: {', '.join(patent_ids)}
"""


class PortfolioValuation:
    """Valuate IP portfolio"""
    
    def __init__(self):
        self.calculator = RoyaltyCalculator()
        
    def value_patent(self, 
                     patent: Dict,
                     market_size: float,
                     penetration: float = 0.01,
                     royalty_rate: float = 0.05,
                     prob_success: float = 0.1) -> Dict:
        """Value a single patent/portfolio"""
        
        # Project revenues
        peak_revenue = market_size * penetration
        royalties = self.calculator.project_royalties(
            peak_sales=peak_revenue,
            royalty_rate=royalty_rate
        )
        
        # Risk-adjusted NPV
        npv = self.calculator.calculate_npv(
            upfront=0,
            annual_royalties=royalties,
            milestones=[]
        )
        
        # Apply probability of success
        risk_adjusted = npv["npv"] * prob_success
        
        return {
            "patent_id": patent.get("id", "unknown"),
            "market_size": market_size,
            "peak_revenue": peak_revenue,
            "npv_unadjusted": npv["npv"],
            "risk_adjusted_npv": risk_adjusted,
            "probability_of_success": prob_success,
            "key_assumptions": {
                "penetration": penetration,
                "royalty_rate": royalty_rate,
                "discount_rate": self.calculator.discount_rate
            }
        }
    
    def value_portfolio(self, patents: List[Dict], correlations: Dict = None) -> Dict:
        """Value entire portfolio with diversification"""
        total_unadjusted = 0
        total_risk_adjusted = 0
        
        for p in patents:
            val = self.value_patent(p, p.get("market_size", 1e9))
            total_unadjusted += val["npv_unadjusted"]
            total_risk_adjusted += val["risk_adjusted_npv"]
            
        # Portfolio diversification discount
        diversification_factor = 0.7 if len(patents) > 5 else 1.0
        
        return {
            "num_patents": len(patents),
            "total_unadjusted_npv": total_unadjusted,
            "total_risk_adjusted_npv": total_risk_adjusted * diversification_factor,
            "diversification_factor": diversification_factor,
            "average_per_patent": total_risk_adjusted / len(patents) if patents else 0
        }


class LicensingManager:
    """Manage licensing workflow"""
    
    def __init__(self, portfolio_path: Path):
        self.portfolio_path = portfolio_path
        self.agreements: Dict[str, LicenseAgreement] = {}
        self.templates = AgreementTemplates()
        self.calculator = RoyaltyCalculator()
        self.valuation = PortfolioValuation()
        self._load_agreements()
        
    def _load_agreements(self):
        """Load existing agreements"""
        agreements_file = self.portfolio_path / "agreements.json"
        if agreements_file.exists():
            with open(agreements_file) as f:
                data = json.load(f)
                self.agreements = {k: LicenseAgreement(**v) for k, v in data.items()}
    
    def _save_agreements(self):
        agreements_file = self.portfolio_path / "agreements.json"
        with open(agreements_file, "w") as f:
            json.dump({k: asdict(v) for k, v in self.agreements.items()}, f, indent=2)
    
    def create_license(self, 
                       patent_ids: List[str],
                       licensee: str,
                       terms: Dict) -> LicenseAgreement:
        """Create new license agreement"""
        license_id = f"LIC_{datetime.now().strftime('%Y%m%d')}_{len(self.agreements)+1:04d}"
        
        agreement = LicenseAgreement(
            license_id=license_id,
            patent_ids=patent_ids,
            licensee=licensee,
            licensor=terms.get("licensor", "Inventor"),
            license_type=terms.get("license_type", "exclusive"),
            territory=terms.get("territory", ["Worldwide"]),
            field_of_use=terms.get("field_of_use", ["therapeutics"]),
            royalty_rate=terms.get("royalty_rate", 0.05),
            minimum_annual_royalty=terms.get("minimum_annual", 25000),
            upfront_fee=terms.get("upfront_fee", 50000),
            milestone_payments=terms.get("milestones", {}),
            start_date=datetime.now().isoformat(),
            end_date=(datetime.now() + timedelta(days=365*terms.get("term_years", 20))).isoformat(),
            status="draft"
        )
        
        self.agreements[license_id] = agreement
        self._save_agreements()
        return agreement
    
    def generate_agreement_document(self, license_id: str) -> str:
        """Generate full agreement document"""
        agreement = self.agreements.get(license_id)
        if not agreement:
            raise ValueError(f"Agreement {license_id} not found")
            
        terms = {
            "field_of_use": agreement.field_of_use,
            "territory": agreement.territory,
            "royalty_rate": agreement.royalty_rate,
            "upfront_fee": agreement.upfront_fee,
            "minimum_annual": agreement.minimum_annual_royalty,
            "milestones": agreement.milestone_payments,
            "term_years": 20,
            "diligence_milestones": {
                "IND filing": "Year 3",
                "Phase I": "Year 4",
                "Phase II": "Year 6",
                "Phase III": "Year 9",
                "BLA/NDA": "Year 11",
                "First commercial sale": "Year 12"
            }
        }
        
        if agreement.license_type == "exclusive":
            return self.templates.exclusive_license(
                agreement.patent_ids, agreement.licensee, terms
            )
        else:
            return self.templates.non_exclusive_license(
                agreement.patent_ids, agreement.licensee, terms
            )
    
    def calculate_deal_npv(self, license_id: str, peak_sales: float) -> Dict:
        """Calculate NPV of a license deal"""
        agreement = self.agreements.get(license_id)
        if not agreement:
            raise ValueError(f"Agreement {license_id} not found")
            
        royalties = self.calculator.project_royalties(
            peak_sales=peak_sales,
            royalty_rate=agreement.royalty_rate
        )
        
        milestones = [
            {"name": k, "payment": v, "year": i+2} 
            for i, (k, v) in enumerate(agreement.milestone_payments.items())
        ]
        
        return self.calculator.calculate_npv(
            upfront=agreement.upfront_fee,
            annual_royalties=royalties,
            milestones=milestones
        )
