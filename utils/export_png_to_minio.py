from datetime import timedelta
from pathlib import Path
import json

from minio import Minio


def _extract_png_path(item):
    if isinstance(item, (str, Path)):
        return Path(item)

    if isinstance(item, dict):
        value = item.get("local_path") or item.get("png_path") or item.get("path") or item.get("file_path")
        if value:
            return Path(value)

    raise TypeError(f"Unsupported png_list item: {type(item).__name__} -> {item!r}")


def export_png_to_minio(png_list):
    bucket_name = "security"

    client = Minio(
        "localhost:9000",
        access_key="minio",
        secret_key="miniosecret",
        secure=False,
    )

    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)

    png_url_map = {}

    for item in png_list:
        png_path = _extract_png_path(item)
        object_name = f"png/{png_path.name}"

        client.fput_object(
            bucket_name,
            object_name,
            str(png_path),
            content_type="image/png",
        )

        presigned_url = client.presigned_get_object(
            bucket_name,
            object_name,
            expires=timedelta(hours=24),
        )

        png_url_map[str(png_path)] = presigned_url

        output_file = Path(f"output/presigned_url/presigned_url_{png_path.stem}.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps({str(png_path): presigned_url}, indent=2))

    return png_url_map