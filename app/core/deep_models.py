"""Deep learning models for multi-horizon border prediction.

Implements a lightweight Temporal Fusion Transformer (TFT) variant with
a monotonic spread output layer that guarantees +2 < +4 < +6 ordering.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import torch
import torch.nn as nn


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    """Configuration for the BorderTFT model."""

    input_dim: int          # number of input features per time step
    future_dim: int = 16    # number of known future calendar features
    d_model: int = 64       # hidden dimension
    n_heads: int = 4        # multi-head attention heads
    n_encoder_layers: int = 2
    n_decoder_layers: int = 1
    dropout: float = 0.1
    max_encoder_len: int = 90   # lookback window (days)
    max_decoder_len: int = 30   # forecast horizon (days)
    n_quantiles: int = 3        # p10, p50, p90
    n_tiers: int = 3            # +2, +4, +6 within a target group


# ---------------------------------------------------------------------------
# Positional Encoding
# ---------------------------------------------------------------------------

class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding."""

    def __init__(self, d_model: int, max_len: int = 500, dropout: float = 0.1) -> None:
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


# ---------------------------------------------------------------------------
# Gated Residual Network (GRN) – core building block of TFT
# ---------------------------------------------------------------------------

class GatedResidualNetwork(nn.Module):
    """Gated Residual Network for variable selection and non-linear processing."""

    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.elu = nn.ELU()
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        self.dropout = nn.Dropout(dropout)
        self.gate = nn.Linear(output_dim, output_dim)
        self.sigmoid = nn.Sigmoid()
        self.layer_norm = nn.LayerNorm(output_dim)
        self.skip = nn.Linear(input_dim, output_dim) if input_dim != output_dim else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.skip(x)
        h = self.elu(self.fc1(x))
        h = self.dropout(self.fc2(h))
        gate = self.sigmoid(self.gate(h))
        return self.layer_norm(gate * h + residual)


# ---------------------------------------------------------------------------
# Monotonic Spread Output Layer
# ---------------------------------------------------------------------------

class MonotonicSpreadHead(nn.Module):
    """Output head that guarantees tier ordering: +2 < +4 < +6.

    Predicts a base value (for the lowest tier +2) and non-negative
    spreads (for +4 - +2 and +6 - +4) using softplus activation.
    The cumulative sum ensures strict monotonicity.

    Output shape: (batch, horizon, n_tiers, n_quantiles)
    """

    def __init__(self, d_model: int, n_tiers: int = 3, n_quantiles: int = 3) -> None:
        super().__init__()
        self.n_tiers = n_tiers
        self.n_quantiles = n_quantiles

        # Base prediction for the lowest tier (+2)
        self.base_head = nn.Linear(d_model, n_quantiles)

        # Non-negative spreads for upper tiers (+4-+2, +6-+4)
        self.spread_heads = nn.ModuleList(
            [nn.Linear(d_model, n_quantiles) for _ in range(n_tiers - 1)]
        )
        self.softplus = nn.Softplus(beta=1.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: (batch, horizon, d_model)

        Returns:
            (batch, horizon, n_tiers, n_quantiles) with guaranteed monotonicity
        """
        base = self.base_head(x)  # (batch, horizon, n_quantiles)
        tiers = [base]
        cumulative = base
        for spread_head in self.spread_heads:
            spread = self.softplus(spread_head(x))  # guaranteed >= 0
            cumulative = cumulative + spread
            tiers.append(cumulative)
        return torch.stack(tiers, dim=2)  # (batch, horizon, n_tiers, n_quantiles)


# ---------------------------------------------------------------------------
# BorderTFT: Main Model
# ---------------------------------------------------------------------------

class BorderTFT(nn.Module):
    """Temporal Fusion Transformer variant for IRIAM border prediction.

    Architecture:
    1. Input projection (GRN) → positional encoding
    2. Transformer encoder (self-attention over historical data)
    3. Transformer decoder (cross-attention: future queries attend to history)
    4. Monotonic spread head (ensures +2 < +4 < +6)

    The decoder uses known future features (calendar, event cycle) as queries.
    """

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.config = config

        # Input projection
        self.input_projection = GatedResidualNetwork(
            config.input_dim, config.d_model * 2, config.d_model, config.dropout
        )

        # Future feature projection (calendar features only, no target lags)
        self.future_projection = GatedResidualNetwork(
            config.future_dim, config.d_model * 2, config.d_model, config.dropout
        )

        self.pos_encoder = PositionalEncoding(config.d_model, max_len=config.max_encoder_len + 50, dropout=config.dropout)
        self.pos_decoder = PositionalEncoding(config.d_model, max_len=config.max_decoder_len + 10, dropout=config.dropout)

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.n_heads,
            dim_feedforward=config.d_model * 4,
            dropout=config.dropout,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=config.n_encoder_layers)

        # Transformer decoder
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=config.d_model,
            nhead=config.n_heads,
            dim_feedforward=config.d_model * 4,
            dropout=config.dropout,
            batch_first=True,
        )
        self.decoder = nn.TransformerDecoder(decoder_layer, num_layers=config.n_decoder_layers)

        # Output head with monotonicity guarantee
        self.output_head = MonotonicSpreadHead(
            config.d_model, n_tiers=config.n_tiers, n_quantiles=config.n_quantiles
        )

    def forward(
        self,
        encoder_input: torch.Tensor,
        decoder_input: torch.Tensor,
        encoder_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            encoder_input: (batch, encoder_len, input_dim) – historical features
            decoder_input: (batch, decoder_len, 16) – known future features
            encoder_mask: (batch, encoder_len) – True for padded positions

        Returns:
            (batch, decoder_len, n_tiers, n_quantiles)
        """
        # Encode historical context
        enc = self.input_projection(encoder_input)   # (B, T_enc, d_model)
        enc = self.pos_encoder(enc)
        if encoder_mask is not None:
            enc = self.encoder(enc, src_key_padding_mask=encoder_mask)
        else:
            enc = self.encoder(enc)

        # Decode future predictions
        dec = self.future_projection(decoder_input)  # (B, T_dec, d_model)
        dec = self.pos_decoder(dec)

        # Causal mask for autoregressive decoding
        tgt_len = dec.size(1)
        causal_mask = nn.Transformer.generate_square_subsequent_mask(tgt_len, device=dec.device)

        out = self.decoder(
            dec,
            enc,
            tgt_mask=causal_mask,
            memory_key_padding_mask=encoder_mask,
        )

        return self.output_head(out)  # (B, T_dec, n_tiers, n_quantiles)


# ---------------------------------------------------------------------------
# Quantile Loss
# ---------------------------------------------------------------------------

class QuantileLoss(nn.Module):
    """Quantile loss for probabilistic forecasting (p10, p50, p90)."""

    def __init__(self, quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)) -> None:
        super().__init__()
        self.quantiles = quantiles

    def forward(self, predictions: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute quantile loss.

        Args:
            predictions: (batch, horizon, n_tiers, n_quantiles)
            targets: (batch, horizon, n_tiers) – actual values

        Returns:
            scalar loss
        """
        targets = targets.unsqueeze(-1)  # (batch, horizon, n_tiers, 1)
        errors = targets - predictions
        losses = []
        for i, q in enumerate(self.quantiles):
            e = errors[..., i]
            loss = torch.max(q * e, (q - 1.0) * e)
            losses.append(loss)
        return torch.stack(losses).mean()
