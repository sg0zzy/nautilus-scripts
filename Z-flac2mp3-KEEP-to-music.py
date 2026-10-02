#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from urllib.parse import unquote, urlparse

import gi
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC

gi.require_version("Notify", "0.7")
from gi.repository import Gio, Notify

DEFAULT_CONVERT_WORKERS = 8
DEFAULT_MAX_STAGED_FLACS = 16

# for checking the queue and temp files:
# watch -n 1 'find /dev/shm/tempmusic -type f -printf "%s %p\n" 2>/dev/null | numfmt --field=1 --to=iec | sort -h'

# OUTPUT_ROOT = Path.home() / "Music" / "mp3"
OUTPUT_ROOT = Path("/media/MP3")
TEMP_ROOT = Path("/dev/shm/tempmusic")
FLAC_INFO_ATTRS = "standard::name,standard::display-name,standard::type"
AUDIO_SUFFIXES = {".flac", ".mp3"}


def positive_int_env(name, default):
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


CONVERT_WORKERS = positive_int_env("FLAC2MP3_CONVERT_WORKERS", DEFAULT_CONVERT_WORKERS)
MAX_STAGED_FLACS = positive_int_env("FLAC2MP3_MAX_STAGED_FLACS", DEFAULT_MAX_STAGED_FLACS)


def show_notification(message):
    try:
        Notify.init("FLAC to MP3")
        Notify.Notification.new("FLAC to MP3", message).show()
    except Exception as exc:
        print(f"Notification failed: {exc}")


def safe_part(value):
    value = (value or "").replace("/", "_").strip()
    return value or "unknown"


def file_display_name(gfile):
    try:
        info = gfile.query_info(FLAC_INFO_ATTRS, Gio.FileQueryInfoFlags.NONE, None)
        return safe_part(info.get_display_name() or info.get_name())
    except Exception:
        basename = gfile.get_basename()
        if basename:
            return safe_part(basename)

        uri_path = unquote(urlparse(gfile.get_uri()).path)
        return safe_part(Path(uri_path).name)


def selected_files_from_nautilus():
    selected = []
    seen = set()

    for arg in sys.argv[1:]:
        gfile = Gio.File.new_for_path(arg)
        uri = gfile.get_uri()
        if uri not in seen:
            seen.add(uri)
            selected.append(gfile)

    selected_uris = os.environ.get("NAUTILUS_SCRIPT_SELECTED_URIS", "")
    for uri in selected_uris.splitlines():
        uri = uri.strip()
        if uri and uri not in seen:
            seen.add(uri)
            selected.append(Gio.File.new_for_uri(uri))

    return selected


def iter_audio_files(gfile, relative_prefix):
    info = gfile.query_info(FLAC_INFO_ATTRS, Gio.FileQueryInfoFlags.NONE, None)
    file_type = info.get_file_type()
    name = safe_part(info.get_display_name() or info.get_name())

    if file_type == Gio.FileType.DIRECTORY:
        enumerator = gfile.enumerate_children(
            FLAC_INFO_ATTRS,
            Gio.FileQueryInfoFlags.NONE,
            None,
        )
        while True:
            child_info = enumerator.next_file(None)
            if child_info is None:
                break

            child_name = safe_part(child_info.get_display_name() or child_info.get_name())
            child = gfile.get_child(child_info.get_name())
            yield from iter_audio_files(child, relative_prefix + [child_name])
        return

    if file_type == Gio.FileType.REGULAR and Path(name).suffix.lower() in AUDIO_SUFFIXES:
        yield gfile, relative_prefix


def output_path_for(relative_parts):
    output_parts = list(relative_parts)
    output_parts[-1] = str(Path(output_parts[-1]).with_suffix(".mp3"))
    return OUTPUT_ROOT.joinpath(*output_parts)


def copy_output_path_for(relative_parts):
    return OUTPUT_ROOT.joinpath(*relative_parts)


def copy_to_temp(gfile, temp_dir, relative_parts):
    suffix = Path(relative_parts[-1]).suffix or ".flac"
    fd, temp_path = tempfile.mkstemp(prefix="flac2mp3-", suffix=suffix, dir=temp_dir)
    os.close(fd)
    os.unlink(temp_path)

    temp_file = Gio.File.new_for_path(temp_path)
    try:
        gfile.copy(
            temp_file,
            Gio.FileCopyFlags.OVERWRITE,
            None,
            None,
        )
        return Path(temp_path)
    except Exception:
        Path(temp_path).unlink(missing_ok=True)
        raise


def copy_tags(flac_path, mp3_path):
    audio = FLAC(flac_path)
    tags = dict(audio.tags or {})
    if not tags:
        return

    mp3 = EasyID3(mp3_path)
    for key, value in tags.items():
        try:
            mp3[key] = value
        except Exception:
            print(f"Couldn't set tag {key} for {mp3_path}")
    mp3.save()


def convert_temp_flac(temp_flac, source_uri, relative_parts):
    mp3_path = output_path_for(relative_parts)
    mp3_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        cmd = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-i",
        str(temp_flac),
        "-map_metadata",
        "0",
        "-id3v2_version",
        "3",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "256k",
        "-write_xing",
        "0",
        "-compression_level",
        "0",
        "-f",
        "mp3",
        str(mp3_path),
        ]
        # cmd = [
        #     "ffmpeg",
        #     "-nostdin",
        #     "-y",
        #     "-i",
        #     str(temp_flac),
        #     "-map_metadata",
        #     "0",
        #     "-id3v2_version",
        #     "3",
        #     "-codec:a",
        #     "libmp3lame",
        #     "-b:a",
        #     "256k",
        #     "-f",
        #     "mp3",
        #     str(mp3_path),
        # ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        copy_tags(temp_flac, mp3_path)
        print(f"Converted: {source_uri} -> {mp3_path}")
        return True
    except Exception as exc:
        print(f"Error processing {source_uri}: {exc}")
        if mp3_path.exists():
            mp3_path.unlink()
        return False
    finally:
        temp_flac.unlink(missing_ok=True)


def submit_conversion(executor, pending_conversions, source_file, relative_parts, temp_dir):
    source_uri = source_file.get_uri()
    try:
        temp_flac = copy_to_temp(source_file, temp_dir, relative_parts)
    except Exception as exc:
        print(f"Error staging {source_uri}: {exc}")
        return False

    future = executor.submit(convert_temp_flac, temp_flac, source_uri, relative_parts)
    pending_conversions.add(future)
    return True


def collect_finished_conversions(futures):
    converted_count = 0
    failed_count = 0

    for future in futures:
        try:
            ok = future.result()
        except Exception as exc:
            print(f"Unexpected conversion worker failure: {exc}")
            ok = False

        if ok:
            converted_count += 1
        else:
            failed_count += 1

    return converted_count, failed_count


def copy_one(source_file, relative_parts, temp_dir):
    temp_mp3 = copy_to_temp(source_file, temp_dir, relative_parts)
    mp3_path = copy_output_path_for(relative_parts)
    mp3_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(temp_mp3, mp3_path)
        print(f"Copied: {source_file.get_uri()} -> {mp3_path}")
        return True
    except Exception as exc:
        print(f"Error copying {source_file.get_uri()}: {exc}")
        if mp3_path.exists():
            mp3_path.unlink()
        return False
    finally:
        temp_mp3.unlink(missing_ok=True)


def selected_root_prefix(gfile):
    info = gfile.query_info(FLAC_INFO_ATTRS, Gio.FileQueryInfoFlags.NONE, None)
    name = safe_part(info.get_display_name() or info.get_name())

    if info.get_file_type() == Gio.FileType.DIRECTORY:
        return [name]

    parent = gfile.get_parent()
    if parent is not None:
        return [file_display_name(parent), name]

    return [name]


def main():
    selected = selected_files_from_nautilus()
    if not selected:
        print("No files or directories selected. Please run this script from Nautilus.")
        return 1

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="run-", dir=TEMP_ROOT))

    converted_count = 0
    copied_count = 0
    failed_count = 0

    pending_conversions = set()

    try:
        with ThreadPoolExecutor(max_workers=CONVERT_WORKERS) as executor:
            for selected_file in selected:
                try:
                    prefix = selected_root_prefix(selected_file)
                    items = list(iter_audio_files(selected_file, prefix))
                except Exception as exc:
                    print(f"Skipping {selected_file.get_uri()}: {exc}")
                    failed_count += 1
                    continue

                for source_file, relative_parts in items:
                    if Path(relative_parts[-1]).suffix.lower() == ".mp3":
                        if copy_one(source_file, relative_parts, temp_dir):
                            copied_count += 1
                        else:
                            failed_count += 1
                        continue

                    while len(pending_conversions) >= MAX_STAGED_FLACS:
                        done, pending_conversions = wait(
                            pending_conversions,
                            return_when=FIRST_COMPLETED,
                        )
                        converted, failed = collect_finished_conversions(done)
                        converted_count += converted
                        failed_count += failed

                    if not submit_conversion(
                        executor,
                        pending_conversions,
                        source_file,
                        relative_parts,
                        temp_dir,
                    ):
                        failed_count += 1

            if pending_conversions:
                done, pending_conversions = wait(pending_conversions)
                converted, failed = collect_finished_conversions(done)
                converted_count += converted
                failed_count += failed
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    message = (
        f"Complete. {converted_count} FLAC files converted and "
        f"{copied_count} MP3 files copied to {OUTPUT_ROOT}."
    )
    if failed_count:
        message += f" {failed_count} failed."
    show_notification(message)
    return 0 if failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
