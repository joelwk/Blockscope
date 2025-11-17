# Contributing to Blockscope

Thank you for your interest in contributing to Blockscope! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/bitcoin.git
   cd bitcoin
   ```

2. **Set up virtual environment**
   ```bash
   ./setup_venv.sh
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -r requirements.txt
   pip install pytest
   ```

4. **Configure your environment**
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your settings, or use environment variables
   ```

## Running Tests

Run the test suite:
```bash
pytest tests/ -v
```

Run specific test files:
```bash
pytest tests/test_buckets.py -v
```

## Code Style Guidelines

- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Keep functions small and focused (single responsibility)
- Extract magic numbers into constants (see `feesentinel/constants.py`)
- Add docstrings to public functions and classes
- Write self-documenting code; use comments to explain "why", not "what"

## Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write tests for new functionality
   - Ensure all tests pass
   - Update documentation as needed

3. **Commit your changes**
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```
   
   Use clear, descriptive commit messages. Follow the format:
   ```
   Short summary (50 chars or less)
   
   More detailed explanation if needed. Wrap at 72 characters.
   Explain what and why vs. how.
   ```

4. **Push and create a pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Pull Request Process

1. Ensure your code follows the style guidelines
2. Make sure all tests pass
3. Update documentation if you've changed functionality
4. Add a clear description of your changes
5. Reference any related issues

## Areas for Contribution

- **Bug fixes**: Fix issues reported in the issue tracker
- **Feature enhancements**: Add new functionality (discuss major features first)
- **Documentation**: Improve README, add examples, clarify usage
- **Tests**: Increase test coverage
- **Code quality**: Refactor for clarity and maintainability

## Questions?

Feel free to open an issue for questions or discussions about contributions.

