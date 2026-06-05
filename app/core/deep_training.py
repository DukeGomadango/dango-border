"""Training pipeline for deep learning border prediction models.

Handles dataset preparation (sliding windows, scaling), training loop
with early stopping, time-series cross-validation, and model serialization.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from app.core.deep_models import BorderTFT, ModelConfig, QuantileLoss
from app.core.features import build_feature_frame, normalize_profile
from app.core.settings import MODELS_DIR, STORAGE_DIR
from app.core.storage import read_json, utc_now_iso, write_json
from app.core.targets import TARGETS_PATH
from app.core.training import _latest_usable_normalized_path, target_to_slug

MODEL_REGISTRY_PATH = STORAGE_DIR / "model_versions.json"
TRAINING_SEED = 42

# Target group definitions: base name → [+2, +4, +6] column names
TARGET_GROUPS: dict[str, list[str]] = {}


def _discover_target_groups(columns: list[str]) -> dict[str, list[str]]:
    """Auto-discover target groups from column names like 'S1 +2', 'S1 +4', 'S1 +6'."""
    groups: dict[str, list[str]] = {}
    pattern = re.compile(r"^(.+)\s*\+(\d+)$")
    for col in columns:
        m = pattern.match(col)
        if m:
            base = m.group(1).strip()
            groups.setdefault(base, []).append(col)
    # Only keep groups with exactly 3 tiers and sort by the numeric suffix
    result = {}
    for base, cols in groups.items():
        if len(cols) == 3:
            cols_sorted = sorted(cols, key=lambda c: int(re.search(r"\+(\d+)", c).group(1)))
            result[base] = cols_sorted
    return result


# ---------------------------------------------------------------------------
# Known future feature columns (purely calendar-based, no data leakage)
# ---------------------------------------------------------------------------

KNOWN_FUTURE_FEATURES = [
    "year", "month", "day", "weekday_num", "quarter",
    "is_month_start", "is_month_end", "week_of_month",
    "event_day", "event_progress", "is_event_start", "is_event_end",
    "is_weekend_in_event",
    "is_holiday_jp", "is_day_before_holiday", "is_day_after_holiday",
    "is_long_weekend_window",
    "is_golden_week", "is_obon", "is_new_year",
]


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class BorderDataset(Dataset):
    """Sliding-window dataset for training the BorderTFT model.

    Each sample consists of:
    - encoder_input: (encoder_len, n_features) historical features + target values
    - decoder_input: (decoder_len, 16) known future calendar features
    - targets: (decoder_len, 3) actual values for the 3 tiers in the forecast window
    - mask: (encoder_len,) True for padded positions
    """

    def __init__(
        self,
        feature_frames: dict[str, pd.DataFrame],
        tier_columns: list[str],
        encoder_len: int = 90,
        decoder_len: int = 7,
        target_scaler: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        self.encoder_len = encoder_len
        self.decoder_len = decoder_len
        self.tier_columns = tier_columns

        # Build aligned multi-tier data from feature frames
        # Use the base tier (+2) as the reference index for alignment
        base_tier = tier_columns[0]
        base_df = feature_frames[base_tier]

        # Get all feature columns (excluding y and date)
        self.feature_cols = [c for c in base_df.columns if c not in ("y", "date")]

        # Find known future feature columns available in the data
        self.future_cols = [c for c in KNOWN_FUTURE_FEATURES if c in base_df.columns]

        # Ensure we have consistent dates across all tiers
        common_dates = set(base_df["date"])
        for tier in tier_columns[1:]:
            common_dates &= set(feature_frames[tier]["date"])

        common_dates_sorted = sorted(common_dates)
        self.dates = common_dates_sorted

        # Build aligned arrays
        n = len(common_dates_sorted)
        self.features_array = np.zeros((n, len(self.feature_cols)), dtype=np.float32)
        self.future_array = np.zeros((n, len(self.future_cols)), dtype=np.float32)
        self.targets_array = np.zeros((n, len(tier_columns)), dtype=np.float32)
        self.targets_valid = np.ones((n, len(tier_columns)), dtype=bool)

        date_to_idx = {d: i for i, d in enumerate(common_dates_sorted)}

        for i, tier in enumerate(tier_columns):
            df = feature_frames[tier]
            for _, row in df.iterrows():
                d = row["date"]
                if d not in date_to_idx:
                    continue
                idx = date_to_idx[d]
                if i == 0:  # only fill features once (from base tier)
                    self.features_array[idx] = [float(row[c]) if pd.notna(row[c]) else 0.0 for c in self.feature_cols]
                    self.future_array[idx] = [float(row[c]) if pd.notna(row[c]) else 0.0 for c in self.future_cols]
                val = row["y"]
                if pd.notna(val):
                    self.targets_array[idx, i] = float(val)
                else:
                    self.targets_valid[idx, i] = False

        # Compute and apply target scaling (per-tier min-max)
        if target_scaler is None:
            self.target_scaler: dict[str, tuple[float, float]] = {}
            for i, tier in enumerate(tier_columns):
                valid = self.targets_array[self.targets_valid[:, i], i]
                if len(valid) > 0:
                    t_min, t_max = float(valid.min()), float(valid.max())
                    if t_max - t_min < 1e-6:
                        t_max = t_min + 1.0
                    self.target_scaler[tier] = (t_min, t_max)
                else:
                    self.target_scaler[tier] = (0.0, 1.0)
        else:
            self.target_scaler = target_scaler

        for i, tier in enumerate(tier_columns):
            t_min, t_max = self.target_scaler[tier]
            self.targets_array[:, i] = (self.targets_array[:, i] - t_min) / (t_max - t_min)

        # Feature scaling (per-column standard scaling)
        self.feature_means = self.features_array.mean(axis=0)
        self.feature_stds = self.features_array.std(axis=0)
        self.feature_stds[self.feature_stds < 1e-8] = 1.0
        self.features_array = (self.features_array - self.feature_means) / self.feature_stds

        # Future feature scaling
        self.future_means = self.future_array.mean(axis=0)
        self.future_stds = self.future_array.std(axis=0)
        self.future_stds[self.future_stds < 1e-8] = 1.0
        self.future_array = (self.future_array - self.future_means) / self.future_stds

        # Generate valid sample indices (need encoder_len + decoder_len contiguous)
        self.samples: list[int] = []
        min_start = self.encoder_len
        max_start = n - self.decoder_len
        for start_idx in range(min_start, max_start):
            # Check that at least some target values exist in the decoder window
            decoder_slice = self.targets_valid[start_idx: start_idx + self.decoder_len]
            if decoder_slice.all(axis=1).any():
                self.samples.append(start_idx)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        start = self.samples[idx]
        enc_start = start - self.encoder_len
        dec_end = start + self.decoder_len

        encoder_input = torch.tensor(self.features_array[enc_start:start], dtype=torch.float32)
        decoder_input = torch.tensor(self.future_array[start:dec_end], dtype=torch.float32)
        targets = torch.tensor(self.targets_array[start:dec_end], dtype=torch.float32)
        target_mask = torch.tensor(self.targets_valid[start:dec_end], dtype=torch.bool)

        return {
            "encoder_input": encoder_input,
            "decoder_input": decoder_input,
            "targets": targets,
            "target_mask": target_mask,
        }


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

@dataclass
class DeepTrainResult:
    """Result from training a deep learning model for a target group."""

    target_group: str
    tier_columns: list[str]
    model_version: str
    model_path: str
    artifact_path: str
    train_loss: float
    val_loss: float
    epochs_trained: int
    target_scaler: dict[str, tuple[float, float]]
    feature_means: list[float]
    feature_stds: list[float]
    future_means: list[float]
    future_stds: list[float]
    feature_cols: list[str]
    future_cols: list[str]


def train_deep_model(
    target_group: str,
    encoder_len: int = 90,
    decoder_len: int = 7,
    epochs: int = 100,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    patience: int = 10,
) -> DeepTrainResult:
    """Train a deep learning model for a target group (e.g., 'S1' → S1+2, S1+4, S1+6)."""
    torch.manual_seed(TRAINING_SEED)
    np.random.seed(TRAINING_SEED)

    normalized_path = _latest_usable_normalized_path()
    if normalized_path is None:
        raise ValueError("No normalized dataset found. Upload and process dataset first.")

    df = pd.read_csv(normalized_path).sort_values("date").reset_index(drop=True)
    groups = _discover_target_groups(list(df.columns))
    if target_group not in groups:
        available = ", ".join(sorted(groups.keys()))
        raise ValueError(f"Target group '{target_group}' not found. Available: {available}")

    tier_columns = groups[target_group]

    # Build feature frames for each tier
    feature_frames: dict[str, pd.DataFrame] = {}
    for tier in tier_columns:
        feature_frames[tier] = build_feature_frame(df, tier, profile="step3")

    # Create dataset
    dataset = BorderDataset(
        feature_frames=feature_frames,
        tier_columns=tier_columns,
        encoder_len=encoder_len,
        decoder_len=decoder_len,
    )

    if len(dataset) < 15:
        raise ValueError(
            f"Not enough training samples for target group '{target_group}' "
            f"(got {len(dataset)}, need >= 15)."
        )

    # Train/val split (time-based: last 20% for validation)
    n = len(dataset)
    split_idx = int(n * 0.8)
    train_indices = list(range(split_idx))
    val_indices = list(range(split_idx, n))

    train_subset = torch.utils.data.Subset(dataset, train_indices)
    val_subset = torch.utils.data.Subset(dataset, val_indices)

    # Load optimized hyperparameters if available
    slug = target_to_slug(target_group)
    best_params_path = MODELS_DIR / f"deep-{slug}" / "best_params.json"
    hparams = {}
    if best_params_path.exists():
        hparams = read_json(best_params_path)

    batch_size_to_use = hparams.get("batch_size", batch_size)
    train_loader = DataLoader(train_subset, batch_size=batch_size_to_use, shuffle=True)
    val_loader = DataLoader(val_subset, batch_size=batch_size_to_use, shuffle=False)

    # Build model
    config = ModelConfig(
        input_dim=len(dataset.feature_cols),
        future_dim=len(dataset.future_cols),
        d_model=hparams.get("d_model", 64),
        n_heads=hparams.get("n_heads", 4),
        n_encoder_layers=hparams.get("n_encoder_layers", 2),
        n_decoder_layers=hparams.get("n_decoder_layers", 1),
        dropout=hparams.get("dropout", 0.1),
        max_encoder_len=encoder_len,
        max_decoder_len=decoder_len,
        n_tiers=len(tier_columns),
    )
    model = BorderTFT(config)
    lr_to_use = hparams.get("learning_rate", learning_rate)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr_to_use, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5
    )
    criterion = QuantileLoss()

    # Training loop with early stopping
    best_val_loss = float("inf")
    best_model_state = None
    epochs_no_improve = 0
    final_train_loss = float("inf")
    final_val_loss = float("inf")
    epochs_trained = 0

    for epoch in range(epochs):
        # Train
        model.train()
        train_losses = []
        for batch in train_loader:
            optimizer.zero_grad()
            output = model(batch["encoder_input"], batch["decoder_input"])
            mask = batch["target_mask"]
            loss = _masked_quantile_loss(criterion, output, batch["targets"], mask)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_losses.append(loss.item())

        # Validate
        model.eval()
        val_losses = []
        with torch.no_grad():
            for batch in val_loader:
                output = model(batch["encoder_input"], batch["decoder_input"])
                mask = batch["target_mask"]
                loss = _masked_quantile_loss(criterion, output, batch["targets"], mask)
                val_losses.append(loss.item())

        avg_train = float(np.mean(train_losses))
        avg_val = float(np.mean(val_losses)) if val_losses else avg_train
        scheduler.step(avg_val)

        final_train_loss = avg_train
        final_val_loss = avg_val
        epochs_trained = epoch + 1

        if avg_val < best_val_loss:
            best_val_loss = avg_val
            best_model_state = copy.deepcopy(model.state_dict())
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                break

    # Restore best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)

    # Save model
    slug = target_to_slug(target_group)
    model_version = f"deep-{slug}-{utc_now_iso().replace(':', '').replace('-', '')}"
    artifact_dir = MODELS_DIR / f"deep-{slug}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    model_path = artifact_dir / f"{model_version}.pt"
    torch.save(model.state_dict(), str(model_path))
    from app.core.r2 import upload_to_r2
    upload_to_r2(model_path)

    # Save artifact metadata
    artifact = {
        "target_group": target_group,
        "tier_columns": tier_columns,
        "model_version": model_version,
        "model_type": "deep_tft",
        "created_at": utc_now_iso(),
        "seed": TRAINING_SEED,
        "config": {
            "input_dim": config.input_dim,
            "future_dim": config.future_dim,
            "d_model": config.d_model,
            "n_heads": config.n_heads,
            "n_encoder_layers": config.n_encoder_layers,
            "n_decoder_layers": config.n_decoder_layers,
            "dropout": config.dropout,
            "max_encoder_len": config.max_encoder_len,
            "max_decoder_len": config.max_decoder_len,
            "n_quantiles": config.n_quantiles,
            "n_tiers": config.n_tiers,
        },
        "training": {
            "encoder_len": encoder_len,
            "decoder_len": decoder_len,
            "epochs_trained": epochs_trained,
            "train_loss": round(final_train_loss, 6),
            "val_loss": round(final_val_loss, 6),
            "batch_size": batch_size,
            "learning_rate": learning_rate,
        },
        "model_path": str(model_path),
        "target_scaler": {k: list(v) for k, v in dataset.target_scaler.items()},
        "feature_cols": dataset.feature_cols,
        "future_cols": dataset.future_cols,
        "feature_means": dataset.feature_means.tolist(),
        "feature_stds": dataset.feature_stds.tolist(),
        "future_means": dataset.future_means.tolist(),
        "future_stds": dataset.future_stds.tolist(),
    }
    artifact_path = artifact_dir / f"{model_version}.json"
    write_json(artifact_path, artifact)

    return DeepTrainResult(
        target_group=target_group,
        tier_columns=tier_columns,
        model_version=model_version,
        model_path=str(model_path),
        artifact_path=str(artifact_path),
        train_loss=round(final_train_loss, 6),
        val_loss=round(final_val_loss, 6),
        epochs_trained=epochs_trained,
        target_scaler=dataset.target_scaler,
        feature_means=dataset.feature_means.tolist(),
        feature_stds=dataset.feature_stds.tolist(),
        future_means=dataset.future_means.tolist(),
        future_stds=dataset.future_stds.tolist(),
        feature_cols=dataset.feature_cols,
        future_cols=dataset.future_cols,
    )


def _masked_quantile_loss(
    criterion: QuantileLoss,
    predictions: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor,
) -> torch.Tensor:
    """Compute quantile loss only on positions where target values are valid."""
    mask_expanded = mask.unsqueeze(-1).expand_as(predictions)
    masked_pred = predictions * mask_expanded
    masked_targets = targets * mask.float()
    return criterion(masked_pred, masked_targets)
