"""Tests for async client cleanup in OpenRouterClient.

Tests for TODO item 4: Add Missing Async Client Cleanup
- Fix async client cleanup in close() method
- Ensure proper event loop handling for async operations
- Add context manager support for async clients
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from openrouter_cli.client import OpenRouterClient


class TestAsyncClientCleanup:
    """Tests for async client cleanup functionality."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        config_manager = MagicMock()
        config_manager.get_api_key.return_value = "test-api-key"
        config_manager.get_base_url.return_value = "https://openrouter.ai/api/v1"
        config_manager.get_timeout.return_value = 120
        config_manager.get_max_retries.return_value = 3
        config_manager.config.defaults.model = "test/model"
        config_manager.config.defaults.temperature = None
        config_manager.config.defaults.max_tokens = None
        config_manager.config.defaults.top_p = None
        config_manager.config.defaults.top_k = None
        config_manager.config.defaults.frequency_penalty = None
        config_manager.config.defaults.presence_penalty = None
        config_manager.config.headers.app_url = "https://test.com"
        config_manager.config.headers.app_name = "test-app"
        return config_manager

    @pytest.fixture
    def client(self, mock_config_manager):
        """Create a client instance for testing."""
        return OpenRouterClient(config_manager=mock_config_manager)

    def test_close_sync_client_only(self, client):
        """Test close() properly closes sync client when no async client exists."""
        # Access sync client to create it
        _ = client.client
        assert client._client is not None
        assert client._async_client is None

        client.close()

        assert client._client is None
        assert client._async_client is None

    def test_close_idempotent(self, client):
        """Test close() can be called multiple times safely."""
        _ = client.client

        client.close()
        client.close()  # Should not raise
        client.close()  # Should not raise

        assert client._client is None

    def test_close_without_any_clients(self, client):
        """Test close() works when no clients were created."""
        assert client._client is None
        assert client._async_client is None

        client.close()  # Should not raise

        assert client._client is None
        assert client._async_client is None

    def test_aclose_method_exists(self, client):
        """Test that aclose() method exists for async cleanup."""
        assert hasattr(client, "aclose")
        assert asyncio.iscoroutinefunction(client.aclose)

    def test_aclose_closes_async_client(self, client):
        """Test aclose() properly closes async client."""

        async def run_test():
            # Access async client to create it
            _ = client.async_client
            assert client._async_client is not None

            await client.aclose()

            assert client._async_client is None

        asyncio.run(run_test())

    def test_aclose_closes_both_clients(self, client):
        """Test aclose() closes both sync and async clients."""

        async def run_test():
            # Create both clients
            _ = client.client
            _ = client.async_client
            assert client._client is not None
            assert client._async_client is not None

            await client.aclose()

            assert client._client is None
            assert client._async_client is None

        asyncio.run(run_test())

    def test_aclose_idempotent(self, client):
        """Test aclose() can be called multiple times safely."""

        async def run_test():
            _ = client.async_client

            await client.aclose()
            await client.aclose()  # Should not raise
            await client.aclose()  # Should not raise

            assert client._async_client is None

        asyncio.run(run_test())

    def test_async_context_manager(self, mock_config_manager):
        """Test async context manager support (__aenter__ and __aexit__)."""

        async def run_test():
            client = OpenRouterClient(config_manager=mock_config_manager)

            async with client as c:
                assert c is client
                # Create clients inside context
                _ = c.client
                _ = c.async_client
                assert c._client is not None
                assert c._async_client is not None

            # After exiting, clients should be closed
            assert client._client is None
            assert client._async_client is None

        asyncio.run(run_test())

    def test_async_context_manager_on_exception(self, mock_config_manager):
        """Test async context manager properly cleans up on exception."""

        async def run_test():
            client = OpenRouterClient(config_manager=mock_config_manager)

            with pytest.raises(ValueError):
                async with client:
                    _ = client.async_client
                    assert client._async_client is not None
                    raise ValueError("Test exception")

            # Cleanup should still happen
            assert client._async_client is None

        asyncio.run(run_test())

    def test_sync_context_manager_still_works(self, client):
        """Test sync context manager (__enter__ and __exit__) still works."""
        with client as c:
            assert c is client
            _ = c.client
            assert c._client is not None

        assert client._client is None

    def test_close_handles_async_client_in_sync_context(self, client):
        """Test close() handles async client cleanup in sync context gracefully."""
        # This is the tricky case - async client exists but we're in sync context
        _ = client.async_client
        assert client._async_client is not None

        # close() should handle this without raising
        client.close()

        assert client._async_client is None

    def test_close_in_async_context_with_running_loop(self, client):
        """Test close() behavior when called within running event loop."""

        async def run_test():
            # Create async client
            _ = client.async_client
            assert client._async_client is not None

            # Call sync close() from within async context
            # This should handle the running loop case
            client.close()

            # Give any scheduled tasks a chance to complete
            await asyncio.sleep(0.01)

            assert client._async_client is None

        asyncio.run(run_test())


class TestCloseResourceWarning:
    """Tests for resource warning behavior in close()."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        config_manager = MagicMock()
        config_manager.get_api_key.return_value = "test-api-key"
        config_manager.get_base_url.return_value = "https://openrouter.ai/api/v1"
        config_manager.get_timeout.return_value = 120
        config_manager.get_max_retries.return_value = 3
        config_manager.config.defaults.model = "test/model"
        config_manager.config.defaults.temperature = None
        config_manager.config.defaults.max_tokens = None
        config_manager.config.defaults.top_p = None
        config_manager.config.defaults.top_k = None
        config_manager.config.defaults.frequency_penalty = None
        config_manager.config.defaults.presence_penalty = None
        config_manager.config.headers.app_url = "https://test.com"
        config_manager.config.headers.app_name = "test-app"
        return config_manager

    def test_close_emits_warning_on_async_cleanup_failure(self, mock_config_manager):
        """Test that close() emits a ResourceWarning when async cleanup fails."""
        client = OpenRouterClient(config_manager=mock_config_manager)

        # Create a mock async client that will fail to close
        mock_async_client = MagicMock()
        mock_async_client.aclose = AsyncMock(side_effect=Exception("Close failed"))
        client._async_client = mock_async_client

        # Should warn but not raise
        with pytest.warns(ResourceWarning, match="Failed to cleanly close async client"):
            client.close()

        # Client reference should still be cleared
        assert client._async_client is None


class TestClientRecreation:
    """Tests for client recreation after close."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        config_manager = MagicMock()
        config_manager.get_api_key.return_value = "test-api-key"
        config_manager.get_base_url.return_value = "https://openrouter.ai/api/v1"
        config_manager.get_timeout.return_value = 120
        config_manager.get_max_retries.return_value = 3
        config_manager.config.defaults.model = "test/model"
        config_manager.config.defaults.temperature = None
        config_manager.config.defaults.max_tokens = None
        config_manager.config.defaults.top_p = None
        config_manager.config.defaults.top_k = None
        config_manager.config.defaults.frequency_penalty = None
        config_manager.config.defaults.presence_penalty = None
        config_manager.config.headers.app_url = "https://test.com"
        config_manager.config.headers.app_name = "test-app"
        return config_manager

    def test_sync_client_can_be_recreated_after_close(self, mock_config_manager):
        """Test sync client can be recreated after close()."""
        client = OpenRouterClient(config_manager=mock_config_manager)

        # Create and close
        first_client = client.client
        assert first_client is not None
        client.close()
        assert client._client is None

        # Recreate
        second_client = client.client
        assert second_client is not None
        assert second_client is not first_client

    def test_async_client_can_be_recreated_after_aclose(self, mock_config_manager):
        """Test async client can be recreated after aclose()."""

        async def run_test():
            client = OpenRouterClient(config_manager=mock_config_manager)

            # Create and close
            first_client = client.async_client
            assert first_client is not None
            await client.aclose()
            assert client._async_client is None

            # Recreate
            second_client = client.async_client
            assert second_client is not None
            assert second_client is not first_client

        asyncio.run(run_test())
