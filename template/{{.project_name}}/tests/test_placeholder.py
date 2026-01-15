"""
Placeholder tests

Replace these tests with actual unit tests for your code.
These tests run locally (not on Databricks) and are executed
by the CI pipeline before bundle validation.
"""

import pytest


class TestPlaceholder:
    """Placeholder test class - replace with your actual tests."""

    def test_example_passes(self):
        """Example test that passes. Replace with actual tests."""
        assert True

    def test_addition(self):
        """Example arithmetic test. Replace with actual tests."""
        assert 1 + 1 == 2

    @pytest.mark.skip(reason="Example of skipped test - remove when adding real tests")
    def test_skipped_example(self):
        """Example of a skipped test."""
        pass
