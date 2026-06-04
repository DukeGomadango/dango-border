#!/usr/bin/env python3
"""Script to train deep learning TFT models for all discoverable target groups."""
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import time
import pandas as pd
from app.core import training, deep_training
from app.core.training import _latest_usable_normalized_path
from app.core.deep_training import train_deep_model, _discover_target_groups

def main():
    print("=== Starting Deep Model Training for All Target Groups ===")
    
    # Load dataset to discover target groups
    normalized_path = _latest_usable_normalized_path()
    if normalized_path is None:
        print("Error: No normalized dataset found.", file=sys.stderr)
        sys.exit(1)
        
    df = pd.read_csv(normalized_path)
    groups = _discover_target_groups(list(df.columns))
    
    print(f"Discovered {len(groups)} target groups: {', '.join(sorted(groups.keys()))}")
    
    results = []
    errors = []
    
    t_start = time.time()
    
    # Train each group
    for idx, target_group in enumerate(sorted(groups.keys()), 1):
        print(f"\n[{idx}/{len(groups)}] Training model for target group: {target_group}...")
        t0 = time.time()
        try:
            # Check training row count
            tier_columns = groups[target_group]
            
            # Run training with full epochs and early stopping
            result = train_deep_model(
                target_group=target_group,
                epochs=100,
                patience=10,
                batch_size=32
            )
            
            duration = time.time() - t0
            print(f"Successfully trained {target_group} in {duration:.1f}s. Val loss: {result.val_loss:.6f}")
            results.append({
                "group": target_group,
                "duration": duration,
                "val_loss": result.val_loss,
                "epochs": result.epochs_trained,
                "version": result.model_version
            })
        except Exception as exc:
            duration = time.time() - t0
            print(f"Error training {target_group}: {exc}")
            errors.append({
                "group": target_group,
                "error": str(exc),
                "duration": duration
            })
            
    total_duration = time.time() - t_start
    print(f"\n=== Training Complete (Total Duration: {total_duration/60:.1f}m) ===")
    print(f"Successfully trained: {len(results)} groups")
    print(f"Failed: {len(errors)} groups")
    
    if errors:
        print("\nErrors encountered:")
        for err in errors:
            print(f"  - {err['group']}: {err['error']}")
            
    print("\nSummary of trained models:")
    print(f"{'Group':8} | {'Val Loss':10} | {'Epochs':6} | {'Time (s)':8} | {'Version':20}")
    print("-" * 65)
    for r in results:
        print(f"{r['group']:8} | {r['val_loss']:10.6f} | {r['epochs']:6} | {r['duration']:8.1f} | {r['version']}")

if __name__ == "__main__":
    main()
