import hashlib
import hmac
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import current_app


class ImageStorageNotConfigured(Exception):
    pass


class ImageStorageError(Exception):
    pass


def upload_product_image(image_data, content_type):
    cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME", "")
    api_key = current_app.config.get("CLOUDINARY_API_KEY", "")
    api_secret = current_app.config.get("CLOUDINARY_API_SECRET", "")
    if not all((cloud_name, api_key, api_secret)):
        raise ImageStorageNotConfigured

    timestamp = str(int(time.time()))
    folder = "egg-chicken/products"
    parameters = {"folder": folder, "timestamp": timestamp}
    signature_payload = "&".join(
        f"{key}={parameters[key]}" for key in sorted(parameters)
    )
    signature = hmac.new(
        api_secret.encode("utf-8"),
        signature_payload.encode("utf-8"),
        hashlib.sha1,
    ).hexdigest()

    boundary = f"----EggChicken{hashlib.sha256(image_data).hexdigest()[:24]}"
    parts = []
    fields = {
        "api_key": api_key,
        "folder": folder,
        "timestamp": timestamp,
        "signature": signature,
    }
    for name, value in fields.items():
        parts.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode("utf-8"),
            b"\r\n",
        ))
    parts.extend((
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="file"; filename="product-image"\r\n',
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        image_data,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ))
    request = Request(
        f"https://api.cloudinary.com/v1_1/{quote(cloud_name, safe='')}/image/upload",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read(1024 * 1024))
    except HTTPError as error:
        current_app.logger.error("Cloud image upload failed with HTTP %s", error.code)
        raise ImageStorageError from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        current_app.logger.error("Cloud image upload could not be completed: %s", error)
        raise ImageStorageError from error

    image_url = result.get("secure_url")
    expected_prefix = f"https://res.cloudinary.com/{cloud_name}/image/upload/"
    if not isinstance(image_url, str) or not image_url.startswith(expected_prefix):
        current_app.logger.error("Cloud image upload returned an invalid image URL")
        raise ImageStorageError
    return image_url
