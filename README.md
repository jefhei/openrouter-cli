# OpenRouter CLI

A command-line interface for interacting with [OpenRouter](https://openrouter.ai) a unified API gateway providing access to 400+ AI models from multiple providers.

## Features

- **Chat completions** with any supported model
- **Streaming responses** for real-time output
- **Model discovery** list, search, and inspect available models
- **Multi-turn conversations** with session persistence
- **Cost tracking** and usage monitoring
- **Configurable parameters** (temperature, max tokens, top_p, etc.)
- **Pipe-friendly** — read prompts from stdin, output to stdout
- **MCP Integration** — connect AI models to external tools:
  - **Filesystem MCP** — read, write, and manage local files
  - **GitHub MCP** — manage repositories, issues, PRs, and workflows

## Installation

```bash
# Using pip
pip install openrouter-cli

# Using pipx (recommended for CLI tools)
pipx install openrouter-cli

# From source
git clone https://github.com/jefhei/openrouter-cli.git
cd openrouter-cli
pip install -e .
```

## Configuration

### API Key Setup

Obtain your API key from [openrouter.ai/keys](https://openrouter.ai/keys), then configure it using one of these methods:

```bash
# Option 1: Environment variable (recommended)
export OPENROUTER_API_KEY="sk-or-v1-..."

# Option 2: Config file
openrouter config set api_key sk-or-v1-...

# Option 3: Pass directly (not recommended for scripts)
openrouter chat --api-key sk-or-v1-... "Hello"
```

### Configuration File

The CLI stores configuration in `~/.config/openrouter/config.toml`:

```toml
[auth]
api_key = "sk-or-v1-..."

[defaults]
model = "anthropic/claude-sonnet-4"
temperature = 1.0
max_tokens = 4096
stream = true

[headers]
# Optional: Identify your app on OpenRouter
app_name = "my-cli-app"
app_url = "https://example.com"
```

## Usage

### Basic Chat

```bash
# Single prompt
openrouter chat "What is the capital of France?"

# Specify a model
openrouter chat -m openai/gpt-4o "Explain quantum computing"

# Interactive mode
openrouter chat --interactive

# Read prompt from stdin
echo "Summarize this text" | openrouter chat -
cat document.txt | openrouter chat - "Summarize the above"
```

### Streaming vs Non-Streaming

```bash
# Stream response in real-time (default)
openrouter chat "Write a short story"

# Wait for complete response
openrouter chat --no-stream "Write a short story"

# Output raw JSON response
openrouter chat --json "Hello"
```

### Model Management

```bash
# List all available models
openrouter models list

# Search for models
openrouter models search "claude"
openrouter models search --provider anthropic

# Get model details
openrouter models info anthropic/claude-sonnet-4

# List models sorted by price
openrouter models list --sort price

# Filter by context length
openrouter models list --min-context 100000
```

### Advanced Parameters

```bash
# Set generation parameters
openrouter chat \
  --temperature 0.7 \
  --max-tokens 2048 \
  --top-p 0.9 \
  --top-k 40 \
  --frequency-penalty 0.5 \
  "Write a creative poem"

# System prompt
openrouter chat \
  --system "You are a helpful coding assistant" \
  "How do I reverse a string in Python?"

# Stop sequences
openrouter chat --stop "END" --stop "DONE" "Generate a list"
```

### Conversations

```bash
# Start a named conversation
openrouter chat --conversation my-project "Let's discuss the architecture"

# Continue the conversation
openrouter chat --conversation my-project "What about the database layer?"

# List saved conversations
openrouter conversations list

# View conversation history
openrouter conversations show my-project

# Delete a conversation
openrouter conversations delete my-project
```

### Cost and Usage

```bash
# Check account credits
openrouter account balance

# View usage statistics
openrouter account usage --period month

# Estimate cost before sending
openrouter chat --dry-run "A very long prompt..."

# Show cost after response
openrouter chat --show-cost "Hello"
```

### Provider Routing

```bash
# Prefer specific providers
openrouter chat \
  --provider anthropic \
  --provider google \
  "Hello"

# Exclude providers
openrouter chat --exclude-provider openai "Hello"

# Require specific parameters support
openrouter chat --require-params tools,json_mode "Hello"
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `chat` | Send a chat completion request |
| `models list` | List available models |
| `models search` | Search models by name or provider |
| `models info` | Get detailed model information |
| `config set` | Set a configuration value |
| `config get` | Get a configuration value |
| `config show` | Display all configuration |
| `account balance` | Check account credit balance |
| `account usage` | View usage statistics |
| `conversations list` | List saved conversations |
| `conversations show` | Display conversation history |
| `conversations delete` | Delete a saved conversation |
| `mcp list` | List configured MCP servers |
| `mcp status` | Show MCP server status |
| `mcp tools` | View available tools from a server |
| `mcp test` | Test MCP server connection |
| `mcp enable` | Enable an MCP server |
| `mcp disable` | Disable an MCP server |
| `version` | Show CLI version |

## Output Formats

```bash
# Default: Human-readable text
openrouter chat "Hello"

# JSON output
openrouter chat --json "Hello"
openrouter models list --json

# Quiet mode (response only, no metadata)
openrouter chat --quiet "Hello"

# Verbose mode (show request/response details)
openrouter chat --verbose "Hello"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | Your API key |  |
| `OPENROUTER_MODEL` | Default model | `openai/gpt-4o-mini` |
| `OPENROUTER_BASE_URL` | API base URL | `https://openrouter.ai/api/v1` |
| `OPENROUTER_TIMEOUT` | Request timeout (seconds) | `120` |
| `OPENROUTER_MAX_RETRIES` | Max retry attempts | `3` |

## Examples

### Piping and Scripting

```bash
# Summarize a file
cat readme.md | openrouter chat - "Summarize this document"

# Generate commit message
git diff --staged | openrouter chat -m anthropic/claude-haiku-4 - \
  "Write a concise commit message for these changes"

# Code review
cat pull_request.diff | openrouter chat \
  --system "You are a senior code reviewer" - \
  "Review this code for bugs and improvements"

# Batch processing
cat prompts.txt | while read line; do
  openrouter chat --quiet "$line" >> responses.txt
done
```

### JSON Mode

```bash
# Request structured JSON output
openrouter chat \
  --json-mode \
  "List 3 countries with their capitals as JSON"

# Parse with jq
openrouter chat --json "Hello" | jq '.choices[0].message.content'
```

### Multi-Modal (Vision)

```bash
# Analyze an image
openrouter chat \
  -m anthropic/claude-sonnet-4 \
  --image screenshot.png \
  "What's in this image?"

# Multiple images
openrouter chat \
  --image photo1.jpg \
  --image photo2.jpg \
  "Compare these two images"

# Image from URL
openrouter chat \
  --image-url "https://example.com/image.png" \
  "Describe this image"
```

### Tool/Function Calling

```bash
# Define tools in a JSON file
openrouter chat \
  --tools tools.json \
  "What's the weather in Tokyo?"

# Inline tool definition
openrouter chat \
  --tool '{"name":"get_time","description":"Get current time"}' \
  "What time is it?"
```

## Error Handling

The CLI uses standard exit codes:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Invalid arguments |
| `3` | Authentication error |
| `4` | Rate limit exceeded |
| `5` | Model not found |
| `6` | Insufficient credits |
| `7` | Network error |

## API Reference

This CLI wraps the OpenRouter API:

- **Base URL:** `https://openrouter.ai/api/v1`
- **Chat completions:** `POST /chat/completions`
- **Models list:** `GET /models`
- **Model info:** `GET /models/{author}/{slug}`
- **Generation stats:** `GET /generation?id={id}`

For full API documentation, visit [openrouter.ai/docs](https://openrouter.ai/docs).

## MCP Filesystem Integration

The CLI supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), enabling AI models to securely interact with your local filesystem. This allows models to read, write, search, and manage files as part of their responses.

### What is MCP?

MCP is an open standard that provides a unified interface for AI models to access external tools and data sources. The filesystem MCP server gives models controlled access to your local files within specified directories.

### Prerequisites

```bash
# Node.js is required for the official MCP filesystem server
node --version  # v18+ recommended

# Or install via nvm
nvm install 20
```

### Enabling Filesystem MCP

```bash
# Enable with specific allowed directories
openrouter mcp enable filesystem ~/Documents ~/Projects

# Enable with current directory
openrouter mcp enable filesystem .

# Disable filesystem MCP
openrouter mcp disable filesystem
```

### Configuration

Add MCP servers to your config file (`~/.config/openrouter/config.toml`):

```toml
[mcp.servers.filesystem]
enabled = true
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem"]
allowed_directories = [
    "~/Documents",
    "~/Projects",
    "/tmp/workspace"
]

# Optional: Use Docker instead
[mcp.servers.filesystem-docker]
enabled = false
command = "docker"
args = [
    "run", "-i", "--rm",
    "--mount", "type=bind,src=${HOME}/Projects,dst=/projects",
    "mcp/filesystem",
    "/projects"
]
```

Or use a dedicated MCP config file (`~/.config/openrouter/mcp.json`):

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/username/Documents",
        "/Users/username/Projects"
      ]
    }
  }
}
```

### Available Filesystem Tools

When MCP filesystem is enabled, models can use these tools:

| Tool | Description |
|------|-------------|
| `read_file` | Read contents of a file |
| `read_multiple_files` | Read multiple files at once |
| `write_file` | Create or overwrite a file |
| `edit_file` | Make selective edits to a file |
| `create_directory` | Create a new directory |
| `list_directory` | List directory contents |
| `directory_tree` | Get recursive tree view |
| `move_file` | Move or rename files/directories |
| `search_files` | Search for files by pattern |
| `get_file_info` | Get file metadata |

### Usage Examples

```bash
# Let the model read and analyze files
openrouter chat --mcp filesystem \
  "Read the README.md in my current project and summarize it"

# Have the model create files
openrouter chat --mcp filesystem \
  "Create a Python script that processes CSV files in ~/Data"

# Code review with file access
openrouter chat --mcp filesystem \
  "Review the code in src/ and suggest improvements"

# Organize files
openrouter chat --mcp filesystem \
  "List all .json files in ~/Projects and describe their structure"

# Multi-turn with file context
openrouter chat --mcp filesystem --interactive
> Read the package.json and tell me about this project
> Now read the main entry point and explain how it works
> Create a new test file based on the patterns you see
```

### MCP Commands

```bash
# List configured MCP servers
openrouter mcp list

# Show server status
openrouter mcp status

# View available tools from a server
openrouter mcp tools filesystem

# Test MCP server connection
openrouter mcp test filesystem

# View MCP server logs
openrouter mcp logs filesystem

# Restart MCP server
openrouter mcp restart filesystem
```

### Tool Filtering

Restrict which MCP tools are available:

```bash
# Allow only read operations
openrouter chat --mcp filesystem \
  --mcp-allow read_file,list_directory,search_files \
  "What files are in my project?"

# Block write operations
openrouter chat --mcp filesystem \
  --mcp-block write_file,edit_file,move_file \
  "Analyze my codebase"
```

Configuration file approach:

```toml
[mcp.servers.filesystem]
enabled = true
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "~/Projects"]

# Only allow these tools
allowed_tools = ["read_file", "list_directory", "search_files"]

# Or block specific tools
# blocked_tools = ["write_file", "edit_file", "move_file"]
```

### Security Considerations

**Important**: MCP filesystem access gives AI models the ability to read and potentially modify files on your system.

**Best Practices:**

1. **Limit directories**: Only allow access to specific directories you need
   ```bash
   # Good: Specific project directory
   openrouter mcp enable filesystem ~/Projects/my-app
   
   # Bad: Entire home directory
   openrouter mcp enable filesystem ~
   ```

2. **Use read-only mode when possible**:
   ```bash
   openrouter chat --mcp filesystem --mcp-readonly "Analyze this code"
   ```

3. **Review before write operations**: Enable confirmation prompts
   ```toml
   [mcp.settings]
   confirm_writes = true
   confirm_deletes = true
   ```

4. **Audit logging**: Track all file operations
   ```bash
   openrouter mcp logs filesystem --tail
   ```

5. **Sandbox with Docker**:
   ```bash
   openrouter mcp enable filesystem-docker \
     --mount ~/Projects:/workspace:ro
   ```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_MCP_ENABLED` | Enable MCP globally | `false` |
| `OPENROUTER_MCP_CONFIG` | Path to MCP config file | `~/.config/openrouter/mcp.json` |
| `OPENROUTER_MCP_TIMEOUT` | Server startup timeout (seconds) | `30` |
| `OPENROUTER_MCP_LOG_LEVEL` | MCP server log level | `warn` |

### Troubleshooting

**Server won't start:**
```bash
# Check Node.js installation
node --version
npx --version

# Test server manually
npx -y @modelcontextprotocol/server-filesystem ~/Documents

# Check logs
openrouter mcp logs filesystem --level debug
```

**Permission denied errors:**
```bash
# Verify directory permissions
ls -la ~/Projects

# Check allowed directories config
openrouter mcp status filesystem
```

**Tools not appearing:**
```bash
# Refresh tool list
openrouter mcp tools filesystem --refresh

# Verify server is running
openrouter mcp test filesystem
```

### Adding Other MCP Servers

The CLI supports any MCP-compatible server:

```toml
# Memory server for persistent context
[mcp.servers.memory]
enabled = true
command = "npx"
args = ["-y", "@modelcontextprotocol/server-memory"]

# Git server for repository operations
[mcp.servers.git]
enabled = true
command = "npx"
args = ["-y", "@modelcontextprotocol/server-git", "--repository", "~/Projects/my-repo"]

# Custom server
[mcp.servers.custom]
enabled = true
command = "/path/to/my-mcp-server"
args = ["--config", "server.json"]
env = { API_KEY = "${CUSTOM_API_KEY}" }
```

Use multiple servers in a single session:

```bash
openrouter chat \
  --mcp filesystem \
  --mcp memory \
  --mcp git \
  "Help me refactor this repository"
```

## MCP GitHub Integration

The CLI supports [GitHub's official MCP Server](https://github.com/github/github-mcp-server), enabling AI models to interact directly with GitHub repositories, issues, pull requests, workflows, and more.

### What Can GitHub MCP Do?

- **Repository Management**: Browse code, search files, analyze commits, create branches
- **Issue & PR Automation**: Create, update, and manage issues and pull requests
- **CI/CD Intelligence**: Monitor GitHub Actions workflows, analyze build failures
- **Code Analysis**: Examine security findings, review Dependabot alerts
- **Team Collaboration**: Access discussions, manage notifications

### Prerequisites

```bash
# Docker is required for the official GitHub MCP server
docker --version  # Ensure Docker is installed and running

# Create a GitHub Personal Access Token
# Visit: https://github.com/settings/tokens
# Grant appropriate scopes (repo, read:org, workflow, etc.)
```

### Configuration

Add the GitHub MCP server to your config file (`~/.config/openrouter/config.toml`):

```toml
[mcp.servers.github]
enabled = true
command = "docker"
args = [
    "run", "-i", "--rm",
    "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
    "ghcr.io/github/github-mcp-server"
]

[mcp.servers.github.env]
GITHUB_PERSONAL_ACCESS_TOKEN = "ghp_your_token_here"
```

### Available GitHub Tools

When GitHub MCP is enabled, models have access to 40+ tools including:

| Category | Tools |
|----------|-------|
| **Repositories** | `search_repositories`, `get_file_contents`, `create_branch`, `push_files`, `create_or_update_file` |
| **Issues** | `list_issues`, `create_issue`, `update_issue`, `add_issue_comment`, `search_issues` |
| **Pull Requests** | `list_pull_requests`, `create_pull_request`, `merge_pull_request`, `get_pull_request_diff` |
| **Actions** | `list_workflows`, `list_workflow_runs`, `get_workflow_run`, `run_workflow` |
| **Users** | `get_me`, `search_users` |
| **Code Security** | `list_code_scanning_alerts`, `list_dependabot_alerts`, `list_secret_scanning_alerts` |

### Usage Examples

```bash
# List your repositories
openrouter chat --mcp github --no-stream \
  "List my recent repositories"

# Create an issue
openrouter chat --mcp github --no-stream \
  "Create an issue in my project-name repo about adding unit tests"

# Search code across repositories
openrouter chat --mcp github --no-stream \
  "Search for Python files using asyncio in my repos"

# Check GitHub Actions status
openrouter chat --mcp github --no-stream \
  "Show me recent workflow runs in my main project"

# Review pull requests
openrouter chat --mcp github --no-stream \
  "List open pull requests in owner/repo and summarize them"

# Analyze repository
openrouter chat --mcp github --no-stream \
  "Analyze the structure of github/github-mcp-server repository"
```

### Combining with Other MCP Servers

Use GitHub MCP alongside filesystem MCP for powerful workflows:

```bash
# Read local files and create GitHub issues
openrouter chat --mcp github --mcp filesystem --no-stream \
  "Read the TODO.md file and create GitHub issues for each item"

# Sync local changes to GitHub
openrouter chat --mcp github --mcp filesystem --no-stream \
  "Read my local README.md and update the one in my GitHub repo"

# Code review with local context
openrouter chat --mcp github --mcp filesystem --no-stream \
  "Compare my local changes with the main branch on GitHub"
```

### MCP Commands for GitHub

```bash
# List available GitHub tools (starts the server)
openrouter mcp tools github --refresh

# Test GitHub server connection
openrouter mcp test github

# View server status
openrouter mcp status
```

### GitHub Enterprise Support

For GitHub Enterprise Server or Enterprise Cloud with data residency:

```toml
[mcp.servers.github]
enabled = true
command = "docker"
args = [
    "run", "-i", "--rm",
    "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
    "-e", "GITHUB_HOST",
    "ghcr.io/github/github-mcp-server"
]

[mcp.servers.github.env]
GITHUB_PERSONAL_ACCESS_TOKEN = "ghp_your_token_here"
GITHUB_HOST = "https://github.your-company.com"
```

### Tool Filtering

Restrict which GitHub tools are available:

```toml
[mcp.servers.github]
enabled = true
command = "docker"
args = ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "ghcr.io/github/github-mcp-server"]

# Only allow read operations
allowed_tools = [
    "get_me",
    "search_repositories", 
    "get_file_contents",
    "list_issues",
    "list_pull_requests"
]

# Or block write operations
# blocked_tools = [
#     "create_issue",
#     "create_pull_request",
#     "push_files",
#     "merge_pull_request"
# ]

[mcp.servers.github.env]
GITHUB_PERSONAL_ACCESS_TOKEN = "ghp_your_token_here"
```

### Security Considerations

**Important**: GitHub MCP gives AI models access to your GitHub account based on your token's permissions.

**Best Practices:**

1. **Minimum scopes**: Only grant necessary token permissions
   - `repo` - Repository access
   - `read:org` - Organization read access
   - `workflow` - GitHub Actions (if needed)

2. **Use separate tokens**: Create dedicated tokens for the CLI
   ```bash
   # Don't reuse tokens from other applications
   ```

3. **Rotate regularly**: Update your token periodically
   ```bash
   openrouter config set mcp.servers.github.env.GITHUB_PERSONAL_ACCESS_TOKEN "ghp_new_token"
   ```

4. **Read-only mode**: Use `--mcp-readonly` for analysis tasks
   ```bash
   openrouter chat --mcp github --mcp-readonly --no-stream "Analyze this repo"
   ```

### Troubleshooting

**Docker image won't pull:**
```bash
# Logout from ghcr.io (clears stale tokens)
docker logout ghcr.io

# Pull explicitly
docker pull ghcr.io/github/github-mcp-server
```

**Server starts but tools don't load:**
```bash
# Test Docker directly
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token"
docker run -i --rm \
  -e GITHUB_PERSONAL_ACCESS_TOKEN \
  ghcr.io/github/github-mcp-server

# Should show: "GitHub MCP Server running on stdio"
```

**Authentication errors:**
```bash
# Verify token is valid
curl -H "Authorization: token ghp_your_token" https://api.github.com/user

# Check token in config
openrouter config show | grep -A5 github
```

**Tools not being used by model:**
```bash
# MCP tools require non-streaming mode
openrouter chat --mcp github --no-stream "List my repos"

# Use verbose mode to debug
openrouter chat --mcp github --no-stream --verbose "List my repos"
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

*Built for the OpenRouter community. Not officially affiliated with OpenRouter.*
