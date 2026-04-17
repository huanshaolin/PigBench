import io
import os

import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"],
    secure=True,
)


def upload_image(image_bytes: bytes, public_id: str) -> str:
    result = cloudinary.uploader.upload(
        io.BytesIO(image_bytes),
        public_id=public_id,
        folder="pigbench/detection",
        resource_type="image",
        overwrite=True,
    )
    return result["secure_url"]


def upload_video(video_path: str, public_id: str) -> str:
    result = cloudinary.uploader.upload(
        video_path,
        public_id=public_id,
        folder="pigbench/tracking",
        resource_type="video",
        overwrite=True,
    )
    return result["secure_url"]
