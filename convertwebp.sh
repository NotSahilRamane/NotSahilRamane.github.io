#!/bin/bash

# Relative path to images folder
IMG_DIR="projects/images"

# Output folder for WebP files (can be inside the same directory)
OUT_DIR="$IMG_DIR/webp"
mkdir -p "$OUT_DIR"

# Quality setting for WebP compression
QUALITY=85

# Convert supported image formats to WebP
find "$IMG_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) | while read -r file; do
  filename=$(basename "$file")
  name="${filename%.*}"
  echo "Converting $filename to $name.webp"
  cwebp -q $QUALITY "$file" -o "$OUT_DIR/$name.webp"
done

echo "✅ Done! WebP images are saved in: $OUT_DIR"
