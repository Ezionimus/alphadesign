from setuptools import setup, find_packages
setup(
    name="alphadesign",
    version="2.0.0",
    description="AI Protein Engineering Platform — Zero-Capital Protein Design",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "torch>=2.0.0",
        "transformers>=4.30.0",
        "biopython>=1.79",
        "pandas>=1.5.0",
        "numpy>=1.24.0",
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0",
        "pyyaml>=6.0",
        "deap>=1.3.0",
    ],
)
