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
    """Syncs the entire storage/ directory from R2 bucket to local.
    Invoked once on startup to restore state.
    """
    if not is_r2_enabled() or r2_client is None or bucket_name is None:
        return

    try:
        logger.info("Syncing storage state from Cloudflare R2...")
        paginator = r2_client.get_paginator("list_objects_v2")
        # List files under storage/ prefix
        pages = paginator.paginate(Bucket=bucket_name, Prefix="storage/")

        downloaded_count = 0
        for page in pages:
            if "Contents" not in page:
                continue
            for obj in page["Contents"]:
                key = obj["Key"]
                if key.endswith("/"):
                    continue

                local_path = BASE_DIR / key
                local_path.parent.mkdir(parents=True, exist_ok=True)

                logger.debug(f"Downloading {key} from R2 to local...")
                r2_client.download_file(
                    Bucket=bucket_name,
                    Key=key,
                    Filename=str(local_path)
                )
                downloaded_count += 1

        logger.info(f"Storage state restored from R2. Downloaded {downloaded_count} files.")
    except Exception as exc:
        logger.error(f"Failed to restore storage from R2: {exc}")
