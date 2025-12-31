# TODO - OpenRouter CLI Improvements

This document contains improvement suggestions for the OpenRouter CLI codebase, organized by priority.

## High Priority

### 1. Fix Account Balance Display Logic
**File:** `src/openrouter_cli/commands/account.py` (Lines 47-75)
- [x] Handle `None` values properly in balance display
- [x] Add validation for pay-as-you-go vs prepaid accounts
- [x] Improve error handling for missing limit field

```python
# Issue: Current code assumes limit exists but API returns None for pay-as-you-go
# Line 58: credits = account_balance.credits can be None
# Line 59: usage = account_balance.usage needs None handling
```

### 2. Add Tool Call Error Handling in Chat
**File:** `src/openrouter_cli/commands/chat.py` (Lines 220-260)
- [x] Add try-catch around tool execution
- [x] Handle JSON parse errors in tool arguments
- [x] Provide better error messages for failed tool calls
- [x] Add validation for MCP tool name parsing

```python
# Lines 246-250: Tool call execution lacks error handling
# Line 244: JSON parsing could fail if model returns invalid arguments
```

### 3. Fix MCP Tool Name Parsing
**File:** `src/openrouter_cli/commands/chat.py` (Lines 243-250)
- [x] Add validation for MCP tool name format (mcp_server_tool)
- [x] Handle cases where tool name doesn't match expected format
- [x] Provide clear error messages

```python
# Lines 243-250: Assumes format "mcp_{server}_{tool}" without validation
```

### 4. Add Missing Async Client Cleanup
**File:** `src/openrouter_cli/client.py` (Lines 220-230)
- [x] Fix async client cleanup in `close()` method
- [x] Ensure proper event loop handling for async operations
- [x] Add context manager support for async clients

```python
# Lines 220-230: Async client cleanup is complex and may fail
# Need better asyncio integration
```

### 5. Add Conversation Token/Cost Tracking
**File:** `src/openrouter_cli/commands/chat.py` (Lines 290-310)
- [ ] Update conversation total_tokens and total_cost after each message
- [ ] Store generation stats when available
- [ ] Handle cases where stats are unavailable

```python
# Lines 290-310: Conversation saving doesn't update tokens/cost
```

## Medium Priority

### 6. Improve Configuration Validation
**File:** `src/openrouter_cli/config.py` (Lines 80-100)
- [ ] Add validation for API key format
- [ ] Validate temperature range (0-2)
- [ ] Add model name validation
- [ ] Implement configuration schema versioning

```python
# Lines 80-100: ConfigManager.load() silently fails on errors
# Line 126: No validation when setting values via set()
```

### 7. Add Rate Limiting Retry Logic
**File:** `src/openrouter_cli/client.py` (Lines 100-120)
- [ ] Implement exponential backoff for rate limits
- [ ] Add configurable retry delay
- [ ] Handle 429 responses with retry-after header

```python
# Lines 100-120: Error handling exists but no retry mechanism
# Line 153: chat_completion doesn't retry on failures
```

### 8. Fix Streaming Tool Call Handling
**File:** `src/openrouter_cli/commands/chat.py` (Lines 190-220)
- [ ] Add streaming support for tool calls
- [ ] Handle partial tool call chunks
- [ ] Support streaming with MCP tools

```python
# Lines 190-220: Streaming mode doesn't handle tool calls
# Only non-streaming mode has tool call loop
```

### 9. Add File Path Validation
**File:** `src/openrouter_cli/commands/chat.py` (Lines 44-70)
- [ ] Validate image paths before base64 encoding
- [ ] Check file size limits
- [ ] Handle permission errors gracefully

```python
# Lines 44-70: read_image_as_base64 lacks size/permission checks
```

### 10. Improve MCP Server Error Recovery
**File:** `src/openrouter_cli/mcp/manager.py` (Lines 60-80)
- [ ] Add automatic server restart on crash
- [ ] Implement health checks
- [ ] Add connection timeout configuration
- [ ] Log server errors to file

```python
# Lines 60-80: _read_responses thread doesn't handle process crashes
# Lines 100-120: _send_request lacks error recovery
```

## Low Priority

### 11. Add Configuration Backup/Restore
**File:** `src/openrouter_cli/config.py` (Lines 180-200)
- [ ] Implement backup command
- [ ] Add restore command
- [ ] Support versioned backups

```python
# Lines 180-200: ConfigManager lacks backup functionality
```

### 12. Add Help Text for All Commands
**File:** `src/openrouter_cli/commands/mcp_cmd.py` (Lines 30-50)
- [ ] Add examples to all MCP commands
- [ ] Improve command descriptions
- [ ] Add troubleshooting tips

```python
# Lines 30-50: enable command needs better examples
```

### 13. Add Conversation Export Options
**File:** `src/openrouter_cli/commands/conversations.py` (Lines 140-160)
- [ ] Add HTML export format
- [ ] Support partial conversation export (date range)
- [ ] Add compression for large conversations

```python
# Lines 140-160: export command only supports JSON and Markdown
```

### 14. Improve Model Filtering Performance
**File:** `src/openrouter_cli/commands/models_cmd.py` (Lines 40-70)
- [ ] Cache model list between calls
- [ ] Add pagination for large result sets
- [ ] Implement lazy loading for model details

```python
# Lines 40-70: list_models fetches all data every time
```

### 15. Add Interactive Mode Enhancements
**File:** `src/openrouter_cli/commands/chat.py` (Lines 265-290)
- [ ] Add command history (up/down arrows)
- [ ] Support multiline input
- [ ] Add auto-completion for commands
- [ ] Implement session persistence

```python
# Lines 265-290: Interactive mode is basic
# No history, no multiline support
```

### 16. Fix chat_old.py Duplication
**File:** `src/openrouter_cli/commands/chat_old.py`
- [ ] Remove duplicate file (identical to chat.py)
- [ ] Update references
- [ ] Document why it exists

```python
# Entire file is duplicated - should be removed
```

### 17. Add Logging Infrastructure
**File:** `src/openrouter_cli/utils/` 
- [ ] Add logging module
- [ ] Implement configurable log levels
- [ ] Log all API requests/responses
- [ ] Add debug mode

```python
# No centralized logging system
# Only console output available
```

### 18. Add Type Hint Improvements
**File:** Multiple files
- [ ] Fix all mypy warnings
- [ ] Add generic types where missing
- [ ] Use TypeAlias for complex types

```python
# Various files have incomplete type hints
```

### 19. Add Configuration Migration
**File:** `src/openrouter_cli/config.py`
- [ ] Add migration system for config version changes
- [ ] Handle breaking changes gracefully
- [ ] Notify users of migration

```python
# No mechanism to handle config format changes
```

### 20. Add Performance Monitoring
**File:** `src/openrouter_cli/client.py`
- [ ] Track API response times
- [ ] Add slow request warnings
- [ ] Monitor token usage patterns

```python
# No performance tracking built-in
```

## Documentation Improvements

### 21. Add Docstrings
**File:** Multiple files
- [ ] Add docstrings to all public functions
- [ ] Document parameters and return values
- [ ] Add examples in docstrings

### 22. Add README Examples
**File:** README.md (if exists)
- [ ] Add common use case examples
- [ ] Document all CLI options
- [ ] Add troubleshooting section

### 23. Add API Error Code Documentation
**File:** `src/openrouter_cli/client.py`
- [ ] Document all error codes
- [ ] Add recovery suggestions
- [ ] Link to OpenRouter docs

## Testing Improvements

### 24. Add Unit Tests
**File:** tests/ (new directory)
- [ ] Test client methods
- [ ] Test configuration handling
- [ ] Test MCP tool execution
- [ ] Test error scenarios

### 25. Add Integration Tests
**File:** tests/integration/
- [ ] Test full chat flow
- [ ] Test MCP server integration
- [ ] Test API error handling
- [ ] Test configuration persistence

---

*Last Updated: 2024*
*Priority: High items should be addressed before next release*