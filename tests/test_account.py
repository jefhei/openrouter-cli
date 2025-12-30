"""Tests for account command."""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

# These imports assume your package structure
# Adjust paths as needed for your actual project
from openrouter_cli.commands.account import account, balance, usage
from openrouter_cli.client import OpenRouterError


class MockAccountBalance:
    """Mock account balance response."""
    def __init__(self, credits=None, usage=None, limit=None):
        self.credits = credits
        self.usage = usage
        self.limit = limit


class TestBalanceCommand:
    """Tests for the balance command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_client(self):
        with patch('openrouter_cli.commands.account.OpenRouterClient') as mock:
            yield mock

    # === Pay-as-you-go account tests ===

    def test_balance_pay_as_you_go_all_none(self, runner, mock_client):
        """Pay-as-you-go account with all None values."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=None,
            usage=None,
            limit=None
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(balance, ['--api-key', 'test-key'])
        
        assert result.exit_code == 0
        assert 'Pay as you go' in result.output or 'pay_as_you_go' in result.output

    def test_balance_pay_as_you_go_with_usage(self, runner, mock_client):
        """Pay-as-you-go account with usage but no credits/limit."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=None,
            usage=5.50,
            limit=None
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(balance, ['--api-key', 'test-key'])
        
        assert result.exit_code == 0
        assert '$5.50' in result.output or '5.50' in result.output

    def test_balance_pay_as_you_go_json_output(self, runner, mock_client):
        """Pay-as-you-go account JSON output."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=None,
            usage=10.00,
            limit=None
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(balance, ['--api-key', 'test-key', '--json'])
        
        assert result.exit_code == 0
        assert '"account_type": "pay_as_you_go"' in result.output
        assert '"limit": null' in result.output

    # === Prepaid account tests ===

    def test_balance_prepaid_positive_credits(self, runner, mock_client):
        """Prepaid account with positive credit balance."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=45.00,
            usage=5.00,
            limit=50.00
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(balance, ['--api-key', 'test-key'])
        
        assert result.exit_code == 0
        assert '$45.00' in result.output or '45.00' in result.output

    def test_balance_prepaid_negative_credits(self, runner, mock_client):
        """Prepaid account with negative credit balance (overage)."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=-5.00,
            usage=55.00,
            limit=50.00
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(balance, ['--api-key', 'test-key'])
        
        assert result.exit_code == 0
        # Should still display without crashing

    def test_balance_prepaid_zero_credits(self, runner, mock_client):
        """Prepaid account with zero credits remaining."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=0.0,
            usage=50.00,
            limit=50.00
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(balance, ['--api-key', 'test-key'])
        
        assert result.exit_code == 0

    def test_balance_prepaid_json_output(self, runner, mock_client):
        """Prepaid account JSON output."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=25.00,
            usage=25.00,
            limit=50.00
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(balance, ['--api-key', 'test-key', '--json'])
        
        assert result.exit_code == 0
        assert '"account_type": "prepaid"' in result.output
        assert '"credits": 25.0' in result.output

    # === Edge cases ===

    def test_balance_credits_none_but_limit_exists(self, runner, mock_client):
        """Edge case: credits is None but limit exists."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=None,
            usage=10.00,
            limit=50.00  # Unusual but possible
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(balance, ['--api-key', 'test-key'])
        
        # Should treat as pay-as-you-go since credits is None
        assert result.exit_code == 0

    def test_balance_missing_limit_attribute(self, runner, mock_client):
        """Edge case: limit attribute doesn't exist on response object."""
        mock_instance = Mock()
        balance_obj = Mock(spec=['credits', 'usage'])  # No 'limit' attribute
        balance_obj.credits = 25.00
        balance_obj.usage = 5.00
        mock_instance.get_account_balance.return_value = balance_obj
        mock_client.return_value = mock_instance

        result = runner.invoke(balance, ['--api-key', 'test-key'])
        
        # Should handle missing attribute gracefully via getattr
        assert result.exit_code == 0

    # === Error handling ===

    def test_balance_api_error(self, runner, mock_client):
        """API error should exit with code 1."""
        mock_instance = Mock()
        mock_instance.get_account_balance.side_effect = OpenRouterError("API Error")
        mock_client.return_value = mock_instance

        result = runner.invoke(balance, ['--api-key', 'test-key'])
        
        assert result.exit_code == 1

    def test_balance_missing_api_key(self, runner, mock_client):
        """Missing API key should raise error."""
        mock_client.side_effect = OpenRouterError("API key required")

        result = runner.invoke(balance)
        
        assert result.exit_code == 1


class TestUsageCommand:
    """Tests for the usage command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_client(self):
        with patch('openrouter_cli.commands.account.OpenRouterClient') as mock:
            yield mock

    def test_usage_default_period(self, runner, mock_client):
        """Usage with default period (month)."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=None,
            usage=15.00,
            limit=None
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(usage, ['--api-key', 'test-key'])
        
        assert result.exit_code == 0
        assert 'month' in result.output.lower()

    def test_usage_week_period(self, runner, mock_client):
        """Usage with week period."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=None,
            usage=5.00,
            limit=None
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(usage, ['--api-key', 'test-key', '--period', 'week'])
        
        assert result.exit_code == 0
        assert 'week' in result.output.lower()

    def test_usage_json_output(self, runner, mock_client):
        """Usage JSON output includes period."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=25.00,
            usage=25.00,
            limit=50.00
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(usage, ['--api-key', 'test-key', '--json', '--period', 'day'])
        
        assert result.exit_code == 0
        assert '"period": "day"' in result.output

    def test_usage_closes_client(self, runner, mock_client):
        """Usage command should close the client."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance()
        mock_client.return_value = mock_instance

        runner.invoke(usage, ['--api-key', 'test-key'])
        
        mock_instance.close.assert_called_once()

    def test_usage_closes_client_on_error(self, runner, mock_client):
        """Usage command should close client even on error."""
        mock_instance = Mock()
        mock_instance.get_account_balance.side_effect = OpenRouterError("Error")
        mock_client.return_value = mock_instance

        runner.invoke(usage, ['--api-key', 'test-key'])
        
        mock_instance.close.assert_called_once()

    def test_usage_none_values(self, runner, mock_client):
        """Usage handles None values correctly."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance(
            credits=None,
            usage=None,
            limit=None
        )
        mock_client.return_value = mock_instance

        result = runner.invoke(usage, ['--api-key', 'test-key'])
        
        assert result.exit_code == 0
        # Usage should default to 0.0 when None


class TestClientCleanup:
    """Tests to verify client is properly closed."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_client(self):
        with patch('openrouter_cli.commands.account.OpenRouterClient') as mock:
            yield mock

    def test_balance_closes_client(self, runner, mock_client):
        """Balance command should close the client."""
        mock_instance = Mock()
        mock_instance.get_account_balance.return_value = MockAccountBalance()
        mock_client.return_value = mock_instance

        runner.invoke(balance, ['--api-key', 'test-key'])
        
        mock_instance.close.assert_called_once()

    def test_balance_closes_client_on_error(self, runner, mock_client):
        """Client should be closed even on error."""
        mock_instance = Mock()
        mock_instance.get_account_balance.side_effect = OpenRouterError("Error")
        mock_client.return_value = mock_instance

        runner.invoke(balance, ['--api-key', 'test-key'])
        
        # With try/finally fix, client is now properly closed on error
        mock_instance.close.assert_called_once()
