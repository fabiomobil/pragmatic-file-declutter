# Skill: Photo Processing

## Supported Formats
- **JPEG** (.jpg, .jpeg): `Pillow` native
- **PNG** (.png): `Pillow` native
- **WebP** (.webp): `Pillow` native
- **HEIC** (.heic, .heif): `pillow-heif` — register with `from pillow_heif import register_heif_opener; register_heif_opener()`
- **RAW** (.cr2, .cr3, .nef, .arw, .dng, .orf, .rw2): `rawpy` — `rawpy.imread(path).postprocess()`
- **TIFF** (.tiff, .tif): `Pillow` native
- **BMP** (.bmp): `Pillow` native
- **GIF** (.gif): `Pillow` native (first frame only)

## Loading Pattern
```python
from PIL import Image
from pillow_heif import register_heif_opener
import rawpy

register_heif_opener()  # Call once at startup

RAW_EXTENSIONS = {".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2"}

def load_image(path: Path) -> Image.Image:
    if path.suffix.lower() in RAW_EXTENSIONS:
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess()
        return Image.fromarray(rgb)
    return Image.open(path)
```

## EXIF Extraction
```python
import exifread

def get_exif(path: Path) -> dict:
    with open(path, "rb") as f:
        tags = exifread.process_file(f, details=False)
    return {str(k): str(v) for k, v in tags.items()}
```

## Video Detection
Extensions to detect and move (don't process): .mp4, .mov, .avi, .mkv, .wmv, .flv, .webm, .m4v, .3gp
