"""Tests for the deep learning model components.

Validates:
1. MonotonicSpreadHead always produces ordered outputs (+2 < +4 < +6)
2. BorderTFT forward pass shapes are correct
3. QuantileLoss computes without errors
4. Event cycle feature generation is correct
"""
from __future__ import annotations

import numpy as np
import pytest
import torch

from app.core.deep_models import BorderTFT, ModelConfig, MonotonicSpreadHead, QuantileLoss


class TestMonotonicSpreadHead:
    """Test that the monotonic spread head guarantees tier ordering."""

    def test_output_is_monotonically_increasing(self) -> None:
        """For any random input, +2 < +4 < +6 must hold across all quantiles."""
        torch.manual_seed(42)
        head = MonotonicSpreadHead(d_model=32, n_tiers=3, n_quantiles=3)
        # Random input simulating decoder output
        x = torch.randn(8, 7, 32)  # (batch=8, horizon=7, d_model=32)
        output = head(x)  # (8, 7, 3, 3)

        assert output.shape == (8, 7, 3, 3)

        # Check monotonicity: tier[i] <= tier[i+1] for all quantiles
        for tier_idx in range(2):
            diff = output[:, :, tier_idx + 1, :] - output[:, :, tier_idx, :]
            assert (diff >= 0).all(), (
                f"Monotonicity violated between tier {tier_idx} and {tier_idx + 1}: "
                f"min diff = {diff.min().item():.6f}"
            )

    def test_monotonicity_with_extreme_inputs(self) -> None:
        """Monotonicity must hold even with extreme input values."""
        torch.manual_seed(123)
        head = MonotonicSpreadHead(d_model=16, n_tiers=3, n_quantiles=3)
        for scale in [0.001, 1.0, 100.0, 10000.0]:
            x = torch.randn(4, 5, 16) * scale
            output = head(x)
            for tier_idx in range(2):
                diff = output[:, :, tier_idx + 1, :] - output[:, :, tier_idx, :]
                assert (diff >= 0).all(), f"Monotonicity violated at scale {scale}"

    def test_monotonicity_after_training_steps(self) -> None:
        """Monotonicity must hold after gradient updates."""
        torch.manual_seed(42)
        head = MonotonicSpreadHead(d_model=16, n_tiers=3, n_quantiles=3)
        optimizer = torch.optim.Adam(head.parameters(), lr=0.01)

        for _ in range(20):
            x = torch.randn(4, 3, 16)
            output = head(x)
            loss = output.mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # Verify monotonicity still holds after training
        head.eval()
        with torch.no_grad():
            x = torch.randn(16, 7, 16)
            output = head(x)
            for tier_idx in range(2):
                diff = output[:, :, tier_idx + 1, :] - output[:, :, tier_idx, :]
                assert (diff >= 0).all()


class TestBorderTFT:
    """Test the full BorderTFT model."""

    def test_forward_pass_shape(self) -> None:
        """Output shape must be (batch, decoder_len, n_tiers, n_quantiles)."""
        config = ModelConfig(input_dim=20, max_encoder_len=30, max_decoder_len=7)
        model = BorderTFT(config)
        model.eval()

        encoder_input = torch.randn(4, 30, 20)
        decoder_input = torch.randn(4, 7, 16)

        with torch.no_grad():
            output = model(encoder_input, decoder_input)

        assert output.shape == (4, 7, 3, 3)

    def test_monotonicity_end_to_end(self) -> None:
        """Full model output must maintain monotonicity."""
        config = ModelConfig(input_dim=10, d_model=32, n_heads=2, max_encoder_len=14, max_decoder_len=7)
        model = BorderTFT(config)
        model.eval()

        encoder_input = torch.randn(8, 14, 10)
        decoder_input = torch.randn(8, 7, 16)

        with torch.no_grad():
            output = model(encoder_input, decoder_input)

        for tier_idx in range(2):
            diff = output[:, :, tier_idx + 1, :] - output[:, :, tier_idx, :]
            assert (diff >= 0).all()

    def test_with_encoder_mask(self) -> None:
        """Model should handle padded encoder inputs."""
        config = ModelConfig(input_dim=10, d_model=16, n_heads=2, max_encoder_len=20, max_decoder_len=5)
        model = BorderTFT(config)
        model.eval()

        encoder_input = torch.randn(2, 20, 10)
        decoder_input = torch.randn(2, 5, 16)
        # Mask: first 5 positions are padding
        mask = torch.zeros(2, 20, dtype=torch.bool)
        mask[:, :5] = True

        with torch.no_grad():
            output = model(encoder_input, decoder_input, encoder_mask=mask)

        assert output.shape == (2, 5, 3, 3)


class TestQuantileLoss:
    """Test the quantile loss function."""

    def test_loss_computes(self) -> None:
        """Loss should return a finite scalar."""
        criterion = QuantileLoss()
        predictions = torch.randn(4, 7, 3, 3)
        targets = torch.randn(4, 7, 3)
        loss = criterion(predictions, targets)
        assert loss.dim() == 0  # scalar
        assert torch.isfinite(loss)

    def test_zero_loss_at_perfect_prediction(self) -> None:
        """Loss should be near zero when predictions match targets."""
        criterion = QuantileLoss(quantiles=(0.5,))
        targets = torch.ones(2, 3, 3)
        # Perfect prediction for median
        predictions = targets.unsqueeze(-1)
        loss = criterion(predictions, targets)
        assert loss.item() < 1e-5


class TestEventCycleFeatures:
    """Test IRIAM event cycle feature computation."""

    def test_event_day_mapping(self) -> None:
        """Tuesday=1, Wednesday=2, ..., Sunday=6, Monday=7."""
        import pandas as pd
        from app.core.features import _add_event_cycle_features

        # Create a week starting from Tuesday 2026-06-09
        dates = pd.date_range("2026-06-09", periods=7, freq="D")
        features = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "weekday_num": dates.weekday,
        })
        _add_event_cycle_features(features)

        expected_event_days = [1, 2, 3, 4, 5, 6, 7]  # Tue=1 ... Mon=7
        assert features["event_day"].tolist() == expected_event_days
        assert features["is_event_start"].tolist() == [1, 0, 0, 0, 0, 0, 0]
        assert features["is_event_end"].tolist() == [0, 0, 0, 0, 0, 0, 1]
        assert features["is_weekend_in_event"].tolist() == [0, 0, 0, 0, 1, 1, 0]

    def test_event_progress(self) -> None:
        """Progress should go from 0.0 (Tue) to 1.0 (Mon)."""
        import pandas as pd
        from app.core.features import _add_event_cycle_features

        dates = pd.date_range("2026-06-09", periods=7, freq="D")
        features = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "weekday_num": dates.weekday,
        })
        _add_event_cycle_features(features)

        progress = features["event_progress"].tolist()
        assert abs(progress[0] - 0.0) < 1e-6  # Tuesday = 0.0
        assert abs(progress[-1] - 1.0) < 1e-6  # Monday = 1.0
