# Contributing to Airbeld Integration

Thank you for your interest in contributing!

## How to Contribute

### Reporting Issues

- Use [GitHub Issues](https://github.com/Embio-Diagnostics/airbeld-ha/issues)
- Search existing issues first
- Provide:
  - Home Assistant version
  - Integration version
  - Error logs (redact sensitive info)
  - Steps to reproduce

### Suggesting Features

- Open an issue with the "enhancement" label
- Describe the use case
- Explain expected behavior

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test locally (see [DEVELOPMENT.md](DEVELOPMENT.md))
5. Run validation before committing:

   ```bash
   ./scripts/lint && ./scripts/validate
   ```

6. Commit with clear messages
7. Push to your fork
8. Open a Pull Request

### Development Setup

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development instructions.

### Code Style

- Follow Home Assistant code style
- Use type hints
- Add docstrings to functions
- Keep code async

## Questions?

Open a [Discussion](https://github.com/Embio-Diagnostics/airbeld-ha/discussions) for questions.

Thank you for contributing! 🎉
