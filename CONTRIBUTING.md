# Contributing to DocMine

First off, thanks for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to DocMine. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Code of Conduct

Be respectful and inclusive. We're all here to build something useful together.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include as many details as possible:

- Use a clear and descriptive title
- Describe the exact steps to reproduce the problem
- Provide specific examples (code snippets, PDF files if possible)
- Describe the behavior you observed and what you expected
- Include your environment details (OS, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- Use a clear and descriptive title
- Provide a detailed description of the proposed functionality
- Explain why this enhancement would be useful
- List any alternative solutions you've considered

### Pull Requests

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. Ensure your code follows the existing style (PEP 8)
4. Make sure your code has proper docstrings and type hints
5. Update the README.md if you're adding new features
6. Write a clear commit message

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/docmine.git
cd docmine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Run tests
python test_basic.py
```

## Styleguide

### Python Styleguide

- Follow PEP 8
- Use type hints for all function parameters and return values
- Write docstrings for all classes and functions (Google style)
- Maximum line length: 100 characters
- Use meaningful variable names

Example:
```python
def extract_text(pdf_path: Path, min_chars: int = 50) -> List[str]:
    """
    Extract text from a PDF file.

    Args:
        pdf_path: Path to the PDF file
        min_chars: Minimum characters required per page

    Returns:
        List of text strings from each page
    """
    # Implementation here
    pass
```

### Git Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests after the first line

Good examples:
```
Add support for scanned PDFs
Fix memory leak in chunker
Update documentation for search API
```

## Project Structure

```
docmine/
├── docmine/           # Main package
│   ├── ingest/       # PDF extraction and chunking
│   ├── storage/      # Database backends
│   └── search/       # Search and embeddings
└── test_basic.py     # Tests
```

## Areas for Contribution

Here are some areas where we'd love contributions:

- **Performance**: Optimize chunking or embedding generation
- **Features**: Add support for more document formats (DOCX, HTML, etc.)
- **Tests**: Expand test coverage
- **Documentation**: Improve examples and use cases
- **Bug fixes**: Check the issues page

## Questions?

Feel free to open an issue with the question label, or reach out to the maintainers.

Thanks for contributing! 🚀
