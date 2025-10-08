# Contributing to StreamAlchemy

Thank you for your interest in contributing to StreamAlchemy! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Git
- FFmpeg
- Basic understanding of video streaming concepts

### Development Setup
1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/StreamAlchemy.git
   cd StreamAlchemy
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   cd python_interface
   pip install -r requirements.txt
   ```
5. Run the application:
   ```bash
   ./run.sh
   ```

## 🐛 Reporting Issues

Before creating an issue, please:
1. Check if the issue already exists
2. Search the documentation
3. Try the latest version

When reporting an issue, include:
- **OS and version**
- **Python version**
- **FFmpeg version**
- **Steps to reproduce**
- **Expected vs actual behavior**
- **Logs** (if applicable)

## 🔧 Making Changes

### Code Style
- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions focused and small

### Testing
- Test your changes thoroughly
- Run the automated tester: `python automated_tester.py`
- Test with different video formats and sources
- Verify health monitoring works correctly

### Commit Messages
Use clear, descriptive commit messages:
```
feat: add support for new video codec
fix: resolve memory leak in stream monitoring
docs: update installation instructions
```

## 📝 Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and test thoroughly

3. **Update documentation** if needed

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request** with:
   - Clear description of changes
   - Reference any related issues
   - Screenshots (for UI changes)
   - Testing notes

## 🎯 Areas for Contribution

### High Priority
- **Windows Support** - Improve Windows compatibility
- **Docker Improvements** - Better containerization
- **API Documentation** - REST API documentation
- **Performance Optimization** - Memory and CPU improvements

### Medium Priority
- **Additional Codecs** - Support for more video/audio codecs
- **Stream Analytics** - Usage statistics and monitoring
- **Authentication** - User management and security
- **Mobile UI** - Better mobile experience

### Low Priority
- **Plugin System** - Extensible architecture
- **Cloud Integration** - AWS/Azure/GCP support
- **Advanced Scheduling** - Cron-like stream scheduling
- **Multi-language Support** - Internationalization

## 🧪 Testing

### Automated Testing
```bash
cd python_interface
python automated_tester.py
```

### Manual Testing Checklist
- [ ] RTSP stream creation and playback
- [ ] Local video file streaming
- [ ] YouTube video streaming
- [ ] Stream health monitoring
- [ ] Web interface functionality
- [ ] Log viewing and search
- [ ] Stream persistence after restart

### Test Data
- Use the provided `sample.mp4` for testing
- Test with various video formats
- Test with different resolutions and codecs

## 📚 Documentation

### Code Documentation
- Add docstrings to new functions
- Update inline comments for complex logic
- Document configuration options

### User Documentation
- Update README.md for new features
- Add examples and use cases
- Document configuration options

## 🔒 Security

### Security Considerations
- Validate all user inputs
- Sanitize file paths and URLs
- Use secure defaults
- Report security issues privately

### Reporting Security Issues
For security vulnerabilities, please email: security@streamalchemy.dev

## 🏷️ Release Process

### Version Numbering
We use [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist
- [ ] Update version numbers
- [ ] Update CHANGELOG.md
- [ ] Test all functionality
- [ ] Update documentation
- [ ] Create release notes

## 💬 Community

### Communication
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **Pull Requests**: Code contributions

### Code of Conduct
Please be respectful and constructive in all interactions. We follow the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## 🎉 Recognition

Contributors will be:
- Listed in the README.md
- Mentioned in release notes
- Given credit in the project documentation

## 📞 Getting Help

- **Documentation**: Check the README and wiki
- **Issues**: Search existing issues first
- **Discussions**: Use GitHub Discussions for questions
- **Email**: For private matters, contact the maintainers

Thank you for contributing to StreamAlchemy! 🚀
