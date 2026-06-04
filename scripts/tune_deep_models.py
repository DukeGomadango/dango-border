#!/usr/bin/env python3
"""Script to tune hyper-parameters of BorderTFT models using Optuna.

Finds the mathematically optimal model parameters (d_model, n_heads, layers,
dropout, learning rate) for a given target group and saves them to models directory.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import copy
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import optuna

from app.core.deep_models import BorderTFT, ModelConfig, QuantileLoss
from app.core.deep_training import (
    BorderDataset,
    _discover_target_groups,
    _masked_quantile_loss,
    KNOWN_FUTURE_FEATURES,
    TRAINING_SEED
)
from app.core.features import build_feature_frame
from app.core.training import _latest_usable_normalized_path, target_to_slug
from app.core.settings import MODELS_DIR
from app.core.storage import write_json

def parse_args():
    parser = argparse.ArgumentParser(description="Tune TFT model using Optuna.")
    parser.add_argument("--group", type=str, default="S1", help="Target group to tune (e.g. S1, B1)")
    parser.add_argument("--trials", type=int, default=15, help="Number of HPO trials")
    parser.add_argument("--epochs", type=int, default=20, help="Epochs per trial")
    return parser.parse_args()

def main():
    args = parse_args()
    target_group = args.group
    n_trials = args.trials
    epochs = args.epochs

    print(f"=== Starting Hyper-parameter Tuning for Target Group: {target_group} ===")
    
    # 1. Load dataset
    normalized_path = _latest_usable_normalized_path()
    if not normalized_path:
        print("Error: No normalized dataset found.", file=sys.stderr)
        sys.exit(1)
        
    df = pd.read_csv(normalized_path).sort_values("date").reset_index(drop=True)
    groups = _discover_target_groups(list(df.columns))
    if target_group not in groups:
        print(f"Error: Target group {target_group} not found.", file=sys.stderr)
        sys.exit(1)
        
    tier_columns = groups[target_group]
    
    # Prepare feature frames
    feature_frames = {}
    for tier in tier_columns:
        feature_frames[tier] = build_feature_frame(df, tier, profile="step3")
        
    # Build dataset
    dataset = BorderDataset(
        feature_frames=feature_frames,
        tier_columns=tier_columns,
        encoder_len=90,
        decoder_len=7
    )
    
    if len(dataset) < 20:
        print(f"Error: Not enough samples to tune (got {len(dataset)}, need >= 20).", file=sys.stderr)
        sys.exit(1)
        
    # Split train/val (last 20% for val)
    n = len(dataset)
    split_idx = int(n * 0.8)
    train_indices = list(range(split_idx))
    val_indices = list(range(split_idx, n))
    
    train_subset = torch.utils.data.Subset(dataset, train_indices)
    val_subset = torch.utils.data.Subset(dataset, val_indices)

    # Disable optuna logger verbosity to keep console output clean
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    # Define Objective function
    def objective(trial):
        # Suggest parameters
        # n_heads must divide d_model
        d_model = trial.suggest_categorical("d_model", [32, 64, 128])
        n_heads = trial.suggest_categorical("n_heads", [2, 4, 8])
        
        n_encoder_layers = trial.suggest_int("n_encoder_layers", 1, 3)
        n_decoder_layers = trial.suggest_int("n_decoder_layers", 1, 2)
        dropout = trial.suggest_float("dropout", 0.05, 0.25)
        learning_rate = trial.suggest_float("learning_rate", 2e-4, 3e-3, log=True)
        batch_size = trial.suggest_categorical("batch_size", [16, 32])

        # Setup loaders
        train_loader = DataLoader(train_subset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_subset, batch_size=batch_size, shuffle=False)

        # Build Model
        config = ModelConfig(
            input_dim=len(dataset.feature_cols),
            future_dim=len(dataset.future_cols),
            d_model=d_model,
            n_heads=n_heads,
            n_encoder_layers=n_encoder_layers,
            n_decoder_layers=n_decoder_layers,
            dropout=dropout,
            max_encoder_len=90,
            max_decoder_len=7,
            n_tiers=len(tier_columns)
        )
        
        # Set seeds for reproducibility of weights initialization
        torch.manual_seed(TRAINING_SEED)
        model = BorderTFT(config)
        
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
        criterion = QuantileLoss()

        best_val_loss = float("inf")
        
        # Train for limited epochs
        for epoch in range(epochs):
            model.train()
            for batch in train_loader:
                optimizer.zero_grad()
                output = model(batch["encoder_input"], batch["decoder_input"])
                loss = _masked_quantile_loss(criterion, output, batch["targets"], batch["target_mask"])
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                
            # Validate
            model.eval()
            val_losses = []
            with torch.no_grad():
                for batch in val_loader:
                    output = model(batch["encoder_input"], batch["decoder_input"])
                    loss = _masked_quantile_loss(criterion, output, batch["targets"], batch["target_mask"])
                    val_losses.append(loss.item())
            
            avg_val_loss = np.mean(val_losses) if val_losses else float("inf")
            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                
            # Prune trial if learning is not promising
            trial.report(best_val_loss, epoch)
            if trial.should_prune():
                raise optuna.exceptions.TrialPruned()

        return best_val_loss

    # 3. Run HPO Study
    study = optuna.create_study(direction="minimize")
    print(f"Running {n_trials} optimization trials (epochs per trial: {epochs})...")
    
    t0 = time.time()
    study.optimize(objective, n_trials=n_trials)
    duration = time.time() - t0
    
    print(f"\nOptimization completed in {duration/60:.1f} minutes.")
    print("Best Trial:")
    print(f"  Value (Val Loss): {study.best_value:.6f}")
    print("  Params:")
    for k, v in study.best_params.items():
        print(f"    {k}: {v}")
        
    # 4. Save best hyperparameters to the target group directory
    slug = target_to_slug(target_group)
    artifact_dir = MODELS_DIR / f"deep-{slug}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    best_params_path = artifact_dir / "best_params.json"
    
    write_json(best_params_path, study.best_params)
    print(f"\nSaved optimal hyper-parameters to: [best_params.json](file:///{best_params_path})")

if __name__ == "__main__":
    main()
