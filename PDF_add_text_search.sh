#!/bin/bash

while IFS= read -r file; do
    # skip non-PDF files
    [[ "${file,,}" == *.pdf ]] || continue

    dir="$(dirname "$file")"
    filename="$(basename "$file")"
    base="${filename%.*}"

    output="$dir/${base}_ocr.pdf"

    # avoid overwriting existing files
    if [[ -e "$output" ]]; then
        i=1
        while [[ -e "$dir/${base}_ocr_$i.pdf" ]]; do
            ((i++))
        done
        output="$dir/${base}_ocr_$i.pdf"
    fi

    ocrmypdf \
        -l ita+eng \
        --deskew \
        --rotate-pages \
        --clean \
        --optimize 1 \
        --output-type pdf \
        "$file" \
        "$output"

done <<< "$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS"