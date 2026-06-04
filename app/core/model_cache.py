"""In-memory cache for deep learning (TFT) and LightGBM models.

Both model families are loaded once at server startup via warm_up_all_models()
and kept in memory for the lifetime of the process, eliminating repeated disk
I/O on every prediction request.

Artifact JSONs are cached separately with functools.lru_cache keyed on the
file-path string so that re-training (new file name) automatically causes a
cache miss and reads the latest artifact.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import lightgbm as lgb
import torch

from app.core.deep_models import BorderTFT, ModelConfig
from app.core.settings import MODELS_DIR
from app.core.storage import read_json
from app.core.training import target_to_slug

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal storage
# ---------------------------------------------------------------------------

# { target_group -> (artifact_dict, BorderTFT) }  — TFT models
_model_store: dict[str, tuple[dict[str, object], BorderTFT]] = {}

# { artifact_model_path_str -> lgb.Booster }  — LightGBM boosters
_lgbm_store: dict[str, lgb.Booster] = {}

# All groups that have a deep model directory available
TARGET_GROUPS = [
    "S3", "S2", "S1",
    "A3", "A2", "A1",
    "B3", "B2", "B1",
    "C5", "C4", "C3",
]


# ---------------------------------------------------------------------------
# Artifact JSON cache (disk → memory, keyed by file path string)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=64)
def _cached_read_json(json_path_str: str) -> dict[str, object]:
    """Read and cache an artifact JSON file.  Cache is keyed by the absolute
    path string so that a newly trained model (different file name) causes a
    cache miss and is loaded fresh.
    """
    return read_json(Path(json_path_str))


def _find_latest_artifact_path(target_group: str) -> Path | None:
    """Return the path to the most recently modified artifact JSON for a group,
    excluding ``best_params.json``.
    """
    slug = target_to_slug(target_group)
    artifact_dir = MODELS_DIR / f"deep-{slug}"
    if not artifact_dir.exists():
        return None

    json_files = sorted(
        [p for p in artifact_dir.glob("*.json") if p.name != "best_params.json"],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return json_files[0] if json_files else None


# ---------------------------------------------------------------------------
# Model instantiation (not cached here; use _model_store instead)
# ---------------------------------------------------------------------------

def _build_model(artifact: dict[str, object]) -> BorderTFT:
    """Instantiate a BorderTFT model and load its weights from disk."""
    cfg = artifact["config"]
    config = ModelConfig(
        input_dim=cfg["input_dim"],
        future_dim=cfg.get("future_dim", 16),
        d_model=cfg["d_model"],
        n_heads=cfg["n_heads"],
        n_encoder_layers=cfg["n_encoder_layers"],
        n_decoder_layers=cfg["n_decoder_layers"],
        dropout=cfg["dropout"],
        max_encoder_len=cfg["max_encoder_len"],
        max_decoder_len=cfg["max_decoder_len"],
        n_quantiles=cfg["n_quantiles"],
        n_tiers=cfg["n_tiers"],
    )
    model = BorderTFT(config)
    model_path = artifact["model_path"]
    state_dict = torch.load(model_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    return model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _load_single_group(group: str) -> tuple[str, tuple[dict[str, object], BorderTFT] | None]:
    """Load a single group's model. Returns (group, (artifact, model)) or (group, None) on failure."""
    artifact_path = _find_latest_artifact_path(group)
    if artifact_path is None:
        logger.warning("  ⚠  No deep model found for %s – skipping.", group)
        return group, None
    try:
        artifact = _cached_read_json(str(artifact_path))
        model = _build_model(artifact)
        logger.info("  ✓  Loaded model for %s  (%s)", group, artifact["model_version"])
        return group, (artifact, model)
    except Exception:
        logger.exception("  ✗  Failed to load model for %s.", group)
        return group, None


def warm_up_all_models() -> None:
    """Load all available deep learning models into memory in parallel.

    Called once during FastAPI ``lifespan`` startup.  Uses a thread pool so
    all groups are loaded concurrently, reducing total warm-up time from
    ``N_groups x load_time`` to approximately ``max(load_time)`` (~5 s).
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    logger.info("Warming up deep learning model cache (parallel load) ...")
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=min(len(TARGET_GROUPS), 8)) as pool:
        futures = {pool.submit(_load_single_group, g): g for g in TARGET_GROUPS}
        for future in as_completed(futures):
            group, entry = future.result()
            if entry is not None:
                _model_store[group] = entry

    elapsed = time.perf_counter() - t0
    loaded = len(_model_store)
    logger.info(
        "Model cache ready -- %d/%d groups loaded in %.1f s.",
        loaded, len(TARGET_GROUPS), elapsed,
    )


def get_cached_entry(target_group: str) -> tuple[dict[str, object], BorderTFT]:
    """Retrieve a pre-loaded (artifact, model) pair from the in-memory cache.

    Raises:
        ValueError: if the model for *target_group* was not loaded at startup.
    """
    entry = _model_store.get(target_group)
    if entry is None:
        raise ValueError(
            f"Deep model for '{target_group}' is not available. "
            "Ensure the model was trained before starting the server."
        )
    return entry


def reload_model(target_group: str) -> None:
    """Force-reload a single group's model from disk.

    Call this after training a new model so the cache reflects the latest
    weights without restarting the server.
    """
    artifact_path = _find_latest_artifact_path(target_group)
    if artifact_path is None:
        raise ValueError(f"No deep model found for target group '{target_group}'.")

    # Invalidate the lru_cache entry for this path so read_json re-reads it
    _cached_read_json.cache_clear()

    artifact = _cached_read_json(str(artifact_path))
    model = _build_model(artifact)
    _model_store[target_group] = (artifact, model)
    logger.info("Reloaded TFT model cache for %s  (%s)", target_group, artifact["model_version"])


# ---------------------------------------------------------------------------
# LightGBM booster cache
# ---------------------------------------------------------------------------

def _load_lgbm_from_artifact_path(artifact_path_str: str) -> tuple[str, lgb.Booster] | None:
    """Load a single LightGBM booster from an artifact JSON.

    Returns (model_path_str, booster) or None on failure.
    """
    try:
        artifact = _cached_read_json(artifact_path_str)
        if artifact.get("model_type") != "lightgbm":
            return None
        model_path = artifact.get("model_path")
        if not model_path or not Path(str(model_path)).exists():
            return None
        booster = lgb.Booster(model_file=str(model_path))
        return str(model_path), booster
    except Exception:
        logger.exception("Failed to load LightGBM booster from %s.", artifact_path_str)
        return None


def warm_up_lgbm_models() -> None:
    """Load all active LightGBM models into memory in parallel.

    Reads the model registry to discover which artifact JSON files correspond
    to active LightGBM models, then loads them concurrently.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from app.core.settings import STORAGE_DIR
    from app.core.storage import read_json as _read_json

    registry_path = STORAGE_DIR / "model_versions.json"
    if not registry_path.exists():
        logger.warning("Model registry not found; skipping LightGBM warm-up.")
        return

    registry = _read_json(registry_path)
    models_map = registry.get("models", {})

    artifact_paths: list[str] = []
    for _target, entries in models_map.items():
        for entry in entries:
            if entry.get("active") and entry.get("model_type") == "lightgbm":
                artifact_paths.append(entry["artifact_path"])
                break  # only the active version

    if not artifact_paths:
        logger.info("No active LightGBM models found in registry.")
        return

    logger.info("Warming up %d LightGBM models (parallel load) ...", len(artifact_paths))
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=min(len(artifact_paths), 8)) as pool:
        futures = [pool.submit(_load_lgbm_from_artifact_path, p) for p in artifact_paths]
        for future in futures:
            result = future.result()
            if result is not None:
                model_path_str, booster = result
                _lgbm_store[model_path_str] = booster

    elapsed = time.perf_counter() - t0
    logger.info(
        "LightGBM cache ready -- %d/%d models loaded in %.1f s.",
        len(_lgbm_store), len(artifact_paths), elapsed,
    )


def get_cached_lgbm_booster(model_path: str) -> lgb.Booster:
    """Retrieve a pre-loaded LightGBM booster from the in-memory cache.

    Falls back to loading from disk if the booster is not in the cache
    (e.g., newly trained model not yet reloaded).

    Args:
        model_path: absolute path string stored in the artifact JSON.

    Returns:
        An lgb.Booster ready for prediction.
    """
    booster = _lgbm_store.get(model_path)
    if booster is None:
        # Cold fallback: load from disk and cache for next time
        logger.warning("LightGBM cache miss for %s; loading from disk.", model_path)
        booster = lgb.Booster(model_file=model_path)
        _lgbm_store[model_path] = booster
    return booster


def reload_lgbm_booster(model_path: str) -> None:
    """Force-reload a single LightGBM booster from disk after re-training."""
    if not Path(model_path).exists():
        raise ValueError(f"LightGBM model file not found: {model_path}")
    _lgbm_store[model_path] = lgb.Booster(model_file=model_path)
    logger.info("Reloaded LightGBM booster: %s", model_path)


# ---------------------------------------------------------------------------
# Prediction range cache pre-warmer
# ---------------------------------------------------------------------------

def warm_up_prediction_caches() -> None:
    """Pre-populate get_prediction_date_range for every known tier.

    This eliminates the ~240ms-per-tier cold cost of build_feature_frame that
    users would otherwise experience on the first request for each group.

    Runs in parallel using a thread pool (one thread per unique target string).
    All groups that lack an active model are skipped silently.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from app.core.availability import get_prediction_date_range
    from app.core.settings import STORAGE_DIR
    from app.core.storage import read_json as _read_json

    # Discover all published targets from the model registry
    registry_path = STORAGE_DIR / "model_versions.json"
    if not registry_path.exists():
        logger.warning("Model registry not found; skipping prediction cache warm-up.")
        return

    registry = _read_json(registry_path)
    all_targets: list[str] = list(registry.get("models", {}).keys())

    if not all_targets:
        logger.info("No targets found in registry; skipping prediction cache warm-up.")
        return

    logger.info(
        "Pre-warming prediction date ranges for %d targets (parallel) ...",
        len(all_targets),
    )
    t0 = time.perf_counter()
    success = 0

    def _warm_one(target: str) -> bool:
        try:
            get_prediction_date_range(target)
            return True
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=min(len(all_targets), 8)) as pool:
        futures = {pool.submit(_warm_one, t): t for t in all_targets}
        for future in as_completed(futures):
            if future.result():
                success += 1

    elapsed = time.perf_counter() - t0
    logger.info(
        "Prediction cache ready -- %d/%d targets pre-warmed in %.1f s.",
        success, len(all_targets), elapsed,
    )
