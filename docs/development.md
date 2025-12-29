## Project Structure
```
openrouter-cli/
├── pyproject.toml          # Package configuration, dependencies, entry points
├── README.md               # User documentation
├── LICENSE                 # MIT license
├── CONTRIBUTING.md         # Contribution guidelines
│
├── src/openrouter_cli/     # Main package
│   ├── __init__.py         # Package metadata, version
│   ├── __main__.py         # Entry point for `python -m openrouter_cli`
│   ├── cli.py              # Main CLI group, Click setup
│   ├── client.py           # OpenRouter API client
│   ├── config.py           # Configuration management (TOML loading/saving)
│   ├── models.py           # Pydantic models for API responses
│   ├── exceptions.py       # Custom exception classes, exit codes
│   ├── utils.py            # Shared utilities, formatting helpers
│   │
│   ├── commands/           # CLI command modules
│   │   ├── __init__.py
│   │   ├── chat.py         # `openrouter chat` command
│   │   ├── models.py       # `openrouter models` subcommands
│   │   ├── config.py       # `openrouter config` subcommands
│   │   ├── account.py      # `openrouter account` subcommands
│   │   ├── conversations.py # `openrouter conversations` subcommands
│   │   └── mcp.py          # `openrouter mcp` subcommands
│   │
│   └── mcp/                # MCP integration
│       ├── __init__.py
│       ├── manager.py      # MCP server lifecycle management
│       ├── client.py       # MCP protocol client
│       └── tools.py        # Tool loading and execution
│
├── tests/                  # Test suite
│   ├── conftest.py         # Pytest fixtures
│   ├── test_cli.py         # CLI command tests
│   ├── test_client.py      # API client tests
│   ├── test_config.py      # Configuration tests
│   └── mocks/              # Mock responses for testing
│
└── docs/                   # Extended documentation (optional)
    ├── architecture.md     # System design decisions
    └── mcp-development.md  # MCP integration details
```