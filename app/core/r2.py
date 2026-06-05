import os
import logging
from pathlib import Path
import boto3
from botocore.client import Config
from app.core.settings import BASE_DIR

logger = logging.getLogger("r2_sync")

# R2 Credentials
access_key = os.getenv("R2_ACCESS_KEY_ID")
secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
account_id = os.getenv("R2_ACCOUNT_ID")
bucket_name = os.getenv("R2_BUCKET_NAME")

_r2_enabled = False
r2_client = None

if all([access_key, secret_key, account_id, bucket_name]):
    try:
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        r2_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )
        _r2_enabled = True
        logger.info("Cloudflare R2 storage synchronization enabled.")
    except Exception as exc:
        logger.error(f"Failed to initialize R2 client: {exc}")
else:
    logger.warning("R2 credentials missing. Running in local-only storage mode.")


def is_r2_enabled() -> bool:
    return _r2_enabled


def upload_to_r2(local_path: Path | str) -> None:
    """Uploads a local file in storage/ to Cloudflare R2 bucket.
    The object key is built from the relative path to BASE_DIR.
    """
    if not is_r2_enabled() or r2_client is None or bucket_name is None:
        return

    local_path = Path(local_path).resolve()
    if not local_path.exists():
        logger.debug(f"Local file does not exist, skipping R2 upload: {local_path}")
        return

    try:
        # Resolve path relative to project root
        relative_path = local_path.relative_to(BASE_DIR)
        key = str(relative_path).replace("\\", "/")

        logger.info(f"Uploading {local_path.name} to R2 (key: {key})...")
        r2_client.upload_file(
            Filename=str(local_path),
            Bucket=bucket_name,
            Key=key
        )
        logger.debug(f"Successfully uploaded {key} to R2.")
    except Exception as exc:
        logger.error(f"Failed to upload {local_path} to R2: {exc}")


def download_from_r2() -> None:
    """Syncs critical metadata and active/latest models from R2 bucket to local.
    Optimized to reduce download size and prevent timeouts on Render startup.
    """
    if not is_r2_enabled() or r2_client is None or bucket_name is None:
        return

    import json

    def to_relative_key(path_str: str) -> str:
        if not path_str:
            return ""
        normalized = path_str.replace("\\", "/")
        for prefix in ["storage/models/", "storage/jobs/"]:
            if prefix in normalized:
                idx = normalized.find(prefix)
                return normalized[idx:]
        return ""

    try:
        logger.info("Syncing optimized storage state from Cloudflare R2...")
        paginator = r2_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix="storage/")

        all_objects = {}
        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    all_objects[obj["Key"]] = obj

        keys_to_download = set()

        # 1. Critical metadata files
        for meta_file in ["storage/targets.json", "storage/model_versions.json", "storage/metrics.json"]:
            if meta_file in all_objects:
                keys_to_download.add(meta_file)

        # 2. Latest normalized dataset
        normalized_csvs = [k for k in all_objects.keys() if k.startswith("storage/jobs/") and k.endswith("_normalized.csv")]
        if normalized_csvs:
            normalized_csvs.sort(key=lambda k: all_objects[k]["LastModified"])
            latest_csv = normalized_csvs[-1]
            keys_to_download.add(latest_csv)
            
            job_id = Path(latest_csv).name.replace("_normalized.csv", "")
            job_json = f"storage/jobs/{job_id}.json"
            if job_json in all_objects:
                keys_to_download.add(job_json)

        # Download model_versions.json first to parse active models
        versions_key = "storage/model_versions.json"
        if versions_key in all_objects:
            local_versions = BASE_DIR / versions_key
            local_versions.parent.mkdir(parents=True, exist_ok=True)
            r2_client.download_file(Bucket=bucket_name, Key=versions_key, Filename=str(local_versions))
            
            try:
                with open(local_versions, "r", encoding="utf-8") as f:
                    registry = json.load(f)
                
                for target, entries in registry.get("models", {}).items():
                    active_entries = [e for e in entries if e.get("active")]
                    for entry in active_entries:
                        artifact_key = to_relative_key(entry.get("artifact_path"))
                        if artifact_key and artifact_key in all_objects:
                            keys_to_download.add(artifact_key)
                            if entry.get("model_type") == "lightgbm":
                                lgb_key = artifact_key.replace(".json", ".lgb.txt")
                                if lgb_key in all_objects:
                                    keys_to_download.add(lgb_key)
            except Exception as e:
                logger.error(f"Failed to parse model_versions.json during sync: {e}")

        # 3. Deep models (TFT) - latest .json and .pt in each deep-<group> directory
        deep_keys = [k for k in all_objects.keys() if k.startswith("storage/models/deep-")]
        deep_groups = {}
        for k in deep_keys:
            parts = Path(k).parts
            if len(parts) >= 4:
                group = parts[2]
                deep_groups.setdefault(group, []).append(k)

        for group, group_keys in deep_groups.items():
            jsons = [k for k in group_keys if k.endswith(".json") and not k.endswith("best_params.json")]
            pts = [k for k in group_keys if k.endswith(".pt")]
            best_params = [k for k in group_keys if k.endswith("best_params.json")]
            
            if jsons:
                jsons.sort(key=lambda k: all_objects[k]["LastModified"])
                keys_to_download.add(jsons[-1])
            if pts:
                pts.sort(key=lambda k: all_objects[k]["LastModified"])
                keys_to_download.add(pts[-1])
            if best_params:
                keys_to_download.add(best_params[0])

        # 4. Perform downloads with size check
        downloaded_count = 0
        skipped_count = 0
        for key in keys_to_download:
            local_path = BASE_DIR / key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            obj_size = all_objects[key]["Size"]
            if local_path.exists() and local_path.stat().st_size == obj_size:
                skipped_count += 1
                continue

            logger.info(f"Downloading {key} from R2...")
            r2_client.download_file(
                Bucket=bucket_name,
                Key=key,
                Filename=str(local_path)
            )
            downloaded_count += 1

        logger.info(f"Storage state restored from R2. Downloaded {downloaded_count} files, skipped {skipped_count} unchanged files.")
    except Exception as exc:
        logger.error(f"Failed to restore storage from R2: {exc}")

