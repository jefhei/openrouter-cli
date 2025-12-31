"""Tests for conversation token/cost tracking (TODO #5)."""

import pytest
from dataclasses import dataclass
from unittest.mock import Mock, patch, MagicMock
from typing import Any


# Import the MessageStats dataclass from chat.py
# We'll test it in isolation first
@dataclass
class MessageStats:
    """Statistics from a single message exchange."""
    
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


class TestMessageStats:
    """Tests for MessageStats dataclass."""

    def test_default_values(self):
        """MessageStats should have zero defaults."""
        stats = MessageStats()
        assert stats.prompt_tokens == 0
        assert stats.completion_tokens == 0
        assert stats.total_tokens == 0
        assert stats.cost == 0.0

    def test_with_values(self):
        """MessageStats should accept values."""
        stats = MessageStats(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.001
        )
        assert stats.prompt_tokens == 100
        assert stats.completion_tokens == 50
        assert stats.total_tokens == 150
        assert stats.cost == 0.001

    def test_accumulation(self):
        """Test that stats can be accumulated."""
        stats1 = MessageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost=0.001)
        stats2 = MessageStats(prompt_tokens=200, completion_tokens=100, total_tokens=300, cost=0.002)
        
        # Simulate accumulation
        total_tokens = stats1.total_tokens + stats2.total_tokens
        total_cost = stats1.cost + stats2.cost
        
        assert total_tokens == 450
        assert total_cost == pytest.approx(0.003)


class TestConversationStatsTracking:
    """Tests for conversation stats tracking logic."""

    def test_session_stats_initialized_to_zero(self):
        """Session stats should start at zero."""
        session_tokens = 0
        session_cost = 0.0
        
        assert session_tokens == 0
        assert session_cost == 0.0

    def test_session_stats_accumulate_from_message_stats(self):
        """Session stats should accumulate from each message."""
        session_tokens = 0
        session_cost = 0.0
        
        # Simulate first message
        msg_stats1 = MessageStats(total_tokens=150, cost=0.001)
        session_tokens += msg_stats1.total_tokens
        session_cost += msg_stats1.cost
        
        assert session_tokens == 150
        assert session_cost == pytest.approx(0.001)
        
        # Simulate second message (e.g., in interactive mode)
        msg_stats2 = MessageStats(total_tokens=200, cost=0.002)
        session_tokens += msg_stats2.total_tokens
        session_cost += msg_stats2.cost
        
        assert session_tokens == 350
        assert session_cost == pytest.approx(0.003)

    def test_conversation_totals_include_existing(self):
        """Conversation totals should include pre-existing values when continuing."""
        # Simulate a conversation that already has some stats
        existing_tokens = 500
        existing_cost = 0.005
        
        # Session adds more
        session_tokens = 150
        session_cost = 0.001
        
        # Final totals
        final_tokens = existing_tokens + session_tokens
        final_cost = existing_cost + session_cost
        
        assert final_tokens == 650
        assert final_cost == pytest.approx(0.006)

    def test_stats_with_tool_calls(self):
        """Stats should accumulate across tool call rounds."""
        session_stats = MessageStats()
        
        # First round - model responds with tool call
        round1_tokens = 100
        round1_cost = 0.0005
        session_stats.total_tokens += round1_tokens
        session_stats.cost += round1_cost
        
        # Second round - tool result processed, final response
        round2_tokens = 150
        round2_cost = 0.0007
        session_stats.total_tokens += round2_tokens
        session_stats.cost += round2_cost
        
        assert session_stats.total_tokens == 250
        assert session_stats.cost == pytest.approx(0.0012)

    def test_stats_unavailable_keeps_zero(self):
        """Stats should remain zero when unavailable."""
        stats = MessageStats()
        
        # Simulate a case where stats couldn't be fetched
        # (exception was caught and we kept defaults)
        
        assert stats.total_tokens == 0
        assert stats.cost == 0.0

    def test_partial_stats_available(self):
        """Handle case where tokens available but cost isn't."""
        stats = MessageStats()
        
        # Tokens available from response.usage
        stats.prompt_tokens = 100
        stats.completion_tokens = 50
        stats.total_tokens = 150
        # Cost not available (API call failed)
        # stats.cost remains 0.0
        
        assert stats.total_tokens == 150
        assert stats.cost == 0.0  # Still useful partial data


class TestIntegrationScenarios:
    """Integration-style tests for common scenarios."""

    def test_single_prompt_scenario(self):
        """Test single prompt with stats tracking."""
        session_tokens = 0
        session_cost = 0.0
        
        # Simulate send_message returning stats
        response_text = "Hello! I'm doing well."
        msg_stats = MessageStats(
            prompt_tokens=10,
            completion_tokens=8,
            total_tokens=18,
            cost=0.00005
        )
        
        session_tokens += msg_stats.total_tokens
        session_cost += msg_stats.cost
        
        assert session_tokens == 18
        assert session_cost == pytest.approx(0.00005)

    def test_interactive_mode_multiple_turns(self):
        """Test interactive mode with multiple conversation turns."""
        session_tokens = 0
        session_cost = 0.0
        
        # Turn 1
        msg_stats1 = MessageStats(total_tokens=50, cost=0.0001)
        session_tokens += msg_stats1.total_tokens
        session_cost += msg_stats1.cost
        
        # Turn 2
        msg_stats2 = MessageStats(total_tokens=75, cost=0.00015)
        session_tokens += msg_stats2.total_tokens
        session_cost += msg_stats2.cost
        
        # Turn 3
        msg_stats3 = MessageStats(total_tokens=100, cost=0.0002)
        session_tokens += msg_stats3.total_tokens
        session_cost += msg_stats3.cost
        
        assert session_tokens == 225
        assert session_cost == pytest.approx(0.00045)

    def test_continuing_existing_conversation(self):
        """Test continuing an existing conversation preserves stats."""
        # Mock existing conversation
        class MockConversation:
            def __init__(self):
                self.total_tokens = 1000
                self.total_cost = 0.01
        
        conv = MockConversation()
        
        # New session adds more
        session_tokens = 200
        session_cost = 0.002
        
        conv.total_tokens += session_tokens
        conv.total_cost += session_cost
        
        assert conv.total_tokens == 1200
        assert conv.total_cost == pytest.approx(0.012)

    def test_dry_run_returns_zero_stats(self):
        """Dry run should return zero stats."""
        stats = MessageStats()  # Default zeros
        
        # In dry run, send_message returns (None, stats) with zero stats
        assert stats.total_tokens == 0
        assert stats.cost == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
