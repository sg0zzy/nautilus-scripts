#!/usr/bin/env python3
import os
import sys
import tempfile
from PIL import Image
import gi
gi.require_version('Notify', '0.7')
from gi.repository import Gio, Notify

MAX_SIDE = 1080

def show_notification(message):
    Notify.init("Convert to JPG LQ")
    notification = Notify.Notification.new("Convert to JPG LQ", message)
    notification.show()

def jpeg_path_for(path):
    root, ext = os.path.splitext(path)
    if ext.lower() in (".jpg", ".jpeg"):
        return path
    return root + ".jpg"

def move_to_trash(path):
    file = Gio.File.new_for_path(path)
    if not file.trash(None):
        raise RuntimeError(f"Could not move to trash: {path}")

def resize_to_max_side(img):
    width, height = img.size
    longest_side = max(width, height)
    if longest_side <= MAX_SIDE:
        return img, False

    scale = MAX_SIDE / longest_side
    new_size = (round(width * scale), round(height * scale))
    return img.resize(new_size, Image.Resampling.LANCZOS), True

def save_as_smaller_jpeg(source_path, destination_path):
    destination_dir = os.path.dirname(destination_path) or "."
    fd, temp_path = tempfile.mkstemp(
        prefix=".convert2jpg-lq-",
        suffix=".jpg",
        dir=destination_dir,
    )
    os.close(fd)

    try:
        with Image.open(source_path) as img:
            rgb_img = img.convert("RGB")
            output_img, resized = resize_to_max_side(rgb_img)
            output_img.save(
                temp_path,
                "JPEG",
                quality=85,
                optimize=True,
                progressive=True,
            )

        if source_path == destination_path:
            if not resized and os.path.getsize(temp_path) >= os.path.getsize(source_path):
                os.remove(temp_path)
                print(f"Kept original: {source_path} (already smaller)")
                return "skipped"
            os.replace(temp_path, destination_path)
            action = "Resized and recompressed" if resized else "Recompressed"
            print(f"{action}: {source_path}")
            return "converted"

        os.replace(temp_path, destination_path)
        print(f"Converted: {source_path} -> {destination_path}")
        move_to_trash(source_path)
        print(f"Moved original to trash: {source_path}")
        return "converted"
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

def process_image(path):
    if not path.lower().endswith((".png", ".jpg", ".jpeg")):
        return "ignored"

    destination_path = jpeg_path_for(path)

    try:
        return save_as_smaller_jpeg(path, destination_path)
    except Exception as e:
        print(f"Error processing {path}: {str(e)}")
        return "error"

def process_path(path):
    counts = {"converted": 0, "skipped": 0, "ignored": 0, "error": 0}

    if os.path.isdir(path):
        print(f"Processing images in: {path}")
        for root, dirs, files in os.walk(path):
            for file in files:
                result = process_image(os.path.join(root, file))
                counts[result] += 1
    elif os.path.isfile(path):
        print(f"Processing image: {path}")
        result = process_image(path)
        counts[result] += 1
    else:
        print(f"Skipping: {path} (not a file or directory)")
        counts["ignored"] += 1

    return counts

def add_counts(total_counts, counts):
    for key, value in counts.items():
        total_counts[key] += value

if __name__ == "__main__":
    # Nautilus passes selected files or directories as arguments.
    if len(sys.argv) > 1:
        total_counts = {"converted": 0, "skipped": 0, "ignored": 0, "error": 0}
        for path in sys.argv[1:]:
            add_counts(total_counts, process_path(path))

        show_notification(
            "Conversion complete. "
            f"{total_counts['converted']} converted, "
            f"{total_counts['skipped']} already small, "
            f"{total_counts['error']} errors."
        )
    else:
        print("No file or directory selected. Please run this script from Nautilus.")
