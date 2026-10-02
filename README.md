# Nautilus scripts

Run from Nautilus: right-click → **Scripts**. Scripts act on the selected files/folders.

| Script | What it does | Debian packages |
| --- | --- | --- |
| `rename_files_list.py` | GUI batch rename: **Paste** the selected file list, type one new name per line, **Rename**. Original extension is kept; logs to `rename_files.log`. | `python3-tk` |
| `convert2jpg.py` | Convert .png/.jpg to progressive JPEG q85, keeping the original if it is already smaller; originals go to the trash. | `python3-pil` `python3-gi` `libnotify4` |
| `convert2jpg_LQ.py` | Same as `convert2jpg.py` but downscales longest side to 1080 px (LANCZOS). | `python3-pil` `python3-gi` `libnotify4` |
| `Z-flac2mp3-KEEP-to-music.py` | Batch FLAC→MP3 256k into output root (default `~/Music/mp3`; env `FLAC2MP3_OUTPUT_ROOT`); tags copied, existing .mp3 just copied. Workers: env `FLAC2MP3_CONVERT_WORKERS`. | `ffmpeg` `python3-mutagen` `python3-gi` `libnotify4` |
| `convert_multi_AV1_ABlock.py` | Queue-based AV1 (NVENC) video conversion to `*_av1.mkv`; originals trashed. Background worker pool + zenity notifications. | `ffmpeg` (NVENC/NVIDIA driver), `zenity`, `glib2.0-bin` |
| `split_and_duplicate_pages2.sh` | Burst one PDF into per-page PDFs, then duplicate each page into a 2-page PDF, in a folder named after the input. | `pdftk-java`, `poppler-utils` |
| `PDF_add_text_search.sh` | Adds a searchable OCR text layer to selected PDFs (ita+eng); output written as `_ocr.pdf`. | `ocrmypdf` `tesseract-ocr` `tesseract-ocr-ita` `tesseract-ocr-eng` `poppler-utils` |

Notes:
- `gio trash` (used by the AV1 script) comes from `glib2.0-bin`.
