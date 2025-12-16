from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="docmine",
    version="0.1.0",
    description="Semantic PDF knowledge extraction pipeline",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="DocMine Contributors",
    url="https://github.com/bcfeen/DocMine",
    project_urls={
        "Bug Tracker": "https://github.com/bcfeen/DocMine/issues",
        "Documentation": "https://github.com/bcfeen/DocMine#readme",
        "Source Code": "https://github.com/bcfeen/DocMine",
    },
    packages=find_packages(),
    install_requires=[
        "pymupdf>=1.23.0",
        "chonkie>=0.1.0",
        "sentence-transformers>=2.2.0",
        "duckdb>=0.9.0",
        "numpy>=1.24.0",
        "tqdm>=4.65.0",
    ],
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Text Processing :: Indexing",
    ],
    keywords="pdf extraction semantic-search embeddings vector-database nlp",
)