# wmainfo-py

A modern Python library for parsing WMA/WMV file metadata.

## Overview

`wmainfo-py` provides access to low-level information on WMA (Windows Media Audio) and WMV (Windows Media Video) files. It parses the ASF (Advanced Systems Format) container format to extract:

- All ASF objects with their sizes and offsets
- File information (bitrate, duration, creation date, etc.)
- Metadata tags (title, author, album, etc.)
- Stream properties (audio channels, sample rate, etc.)
- DRM protection status

## Requirements

- Python 3.8 or higher
- No external dependencies (uses only standard library)

## Installation

```bash
# Copy wmainfo.py to your project
cp wmainfo.py /path/to/your/project/
```

## Usage

### Basic Usage

```python
from wmainfo import WmaInfo

# Parse a WMA file
wma = WmaInfo('audio.wma')

# Access metadata tags
print(f"Title: {wma.tags.get('Title', 'Unknown')}")
print(f"Artist: {wma.tags.get('Author', 'Unknown')}")
print(f"Album: {wma.tags.get('AlbumTitle', 'Unknown')}")

# Access file information
print(f"Bitrate: {wma.info.get('bitrate', 0)} kbps")
print(f"Duration: {wma.info.get('playtime_seconds', 0)} seconds")
print(f"File size: {wma.info.get('filesize', 0)} bytes")

# Check for DRM
if wma.has_drm():
    print("This file has DRM protection")
```

### Advanced Usage

```python
from wmainfo import WmaInfo, WmaInfoError

try:
    # Enable debug output
    wma = WmaInfo('video.wmv', debug=True)

    # Check if specific tags exist
    if wma.has_tag('Title'):
        print(f"Title: {wma.tags['Title']}")

    # Print all available information
    wma.print_info()
    wma.print_tags()
    wma.print_objects()

    # Parse stream properties (audio/video codec info)
    wma.parse_stream()
    if wma.stream:
        print(f"Audio channels: {wma.stream.audio_channels}")
        print(f"Sample rate: {wma.stream.audio_sample_rate} Hz")
        print(f"Audio bitrate: {wma.stream.audio_bitrate} bps")

except WmaInfoError as e:
    print(f"Error parsing file: {e}")
```

### Command Line Usage

```bash
# Basic usage
python wmainfo.py audio.wma

# With debug output
python wmainfo.py --debug audio.wma

# Parse stream information
python wmainfo.py --stream video.wmv

# Show only specific information
python wmainfo.py --no-tags --no-objects audio.wma
```

## API Reference

### WmaInfo Class

#### Constructor

```python
WmaInfo(file_path: Union[str, Path], debug: bool = False)
```

Creates a new WmaInfo instance and parses the file header.

**Parameters:**
- `file_path`: Path to the WMA/WMV file
- `debug`: Enable debug output (default: False)

**Raises:**
- `WmaInfoError`: If the file cannot be parsed
- `FileNotFoundError`: If the file doesn't exist

#### Attributes

- `tags` (Dict[str, Any]): Dictionary of metadata tags (ID3-like information)
- `info` (Dict[str, Any]): Dictionary of file properties (bitrate, duration, etc.)
- `header_objects` (Dict[str, ASFObject]): Dictionary of ASF header objects
- `drm` (bool): Whether the file has DRM protection
- `stream` (Optional[StreamInfo]): Stream properties (populated by `parse_stream()`)

#### Methods

##### `has_drm() -> bool`
Returns True if the file has DRM protection.

##### `has_tag(tag: str) -> bool`
Returns True if the specified tag exists and has a non-empty value.

##### `has_info(field: str) -> bool`
Returns True if the specified info field exists and has a non-empty value.

##### `print_tags() -> None`
Pretty-prints all metadata tags to stdout.

##### `print_info() -> None`
Pretty-prints all file information to stdout.

##### `print_objects() -> None`
Prints all ASF header objects to stdout.

##### `parse_stream() -> None`
Parses the ASF Stream Properties Object to extract codec information.

**Raises:**
- `WmaInfoError`: If the stream properties cannot be parsed

### Common Tags

The `tags` dictionary may contain:

- `Title`: Song/video title
- `Author`: Artist name
- `AlbumTitle`: Album name
- `AlbumArtist`: Album artist
- `Genre`: Music genre
- `Year`: Release year
- `TrackNumber`: Track number
- `Copyright`: Copyright information
- `Description`: File description
- `Rating`: Content rating
- `Composer`: Composer name
- `Lyrics`: Song lyrics

### Common Info Fields

The `info` dictionary may contain:

- `filesize`: File size in bytes
- `creation_date_unix`: Creation timestamp (Unix time)
- `creation_string`: Human-readable creation date
- `playtime_seconds`: Duration in seconds
- `bitrate`: Bitrate in kbps
- `max_bitrate`: Maximum bitrate in bps
- `broadcast`: Whether the file is streamable
- `seekable`: Whether seeking is supported
- `min_packet_size`: Minimum packet size
- `max_packet_size`: Maximum packet size

### Stream Properties

After calling `parse_stream()`, the `stream` attribute contains:

- `audio_channels`: Number of audio channels
- `audio_sample_rate`: Sample rate in Hz
- `audio_bitrate`: Audio bitrate in bps
- `audio_bits_per_sample`: Bits per audio sample
- `stream_number`: Stream identifier
- `encrypted`: Whether the stream is encrypted

## Examples

### Extract Album Art

```python
from wmainfo import WmaInfo

wma = WmaInfo('song.wma')

# Check for album art in extended content
if 'Picture' in wma.info:
    picture_data = wma.info['Picture']
    # Picture data includes MIME type and image data
```

### List All Available Metadata

```python
from wmainfo import WmaInfo

wma = WmaInfo('media.wmv')

print("=== Tags ===")
for key, value in wma.tags.items():
    print(f"  {key}: {value}")

print("\n=== Info ===")
for key, value in wma.info.items():
    if not key.startswith('_'):  # Skip internal fields
        print(f"  {key}: {value}")
```

### Batch Process Files

```python
from pathlib import Path
from wmainfo import WmaInfo, WmaInfoError

def process_media_files(directory: Path):
    """Process all WMA/WMV files in a directory."""

    for file_path in directory.rglob('*.wm[av]'):
        try:
            wma = WmaInfo(file_path)

            print(f"\n{file_path.name}")
            print(f"  Duration: {wma.info.get('playtime_seconds', 0)}s")
            print(f"  Bitrate: {wma.info.get('bitrate', 0)} kbps")

            if wma.has_tag('Title'):
                print(f"  Title: {wma.tags['Title']}")
            if wma.has_tag('Author'):
                print(f"  Artist: {wma.tags['Author']}")

            if wma.has_drm():
                print("  ⚠️  Has DRM protection")

        except WmaInfoError as e:
            print(f"Error processing {file_path.name}: {e}")

# Usage
process_media_files(Path('/path/to/media'))
```

## Error Handling

The library raises `WmaInfoError` for parsing errors:

```python
from wmainfo import WmaInfo, WmaInfoError

try:
    wma = WmaInfo('file.wma')
except WmaInfoError as e:
    print(f"Parsing error: {e}")
except FileNotFoundError:
    print("File not found")
except PermissionError:
    print("Permission denied")
```

## Testing

Run the test suite:

```bash
# Run all tests
python -m pytest test_wmainfo.py

# Or using unittest
python -m unittest test_wmainfo.py

# With coverage
python -m pytest --cov=wmainfo test_wmainfo.py
```

## Notes

- The parser follows the ASF specification for Windows Media files
- All strings are decoded from UTF-16LE as per the ASF spec
- File times are converted from Windows FILETIME to Unix timestamps
- The library uses only the Python standard library (no dependencies)

## License

This library is released under the Artistic/Perl license, maintaining compatibility with the original Perl module by Dan Sully.

## Credits

Originally based on Dan Sully's Audio-WMA Perl module. Modernized for Python 3.8+ with type annotations, context managers, and current best practices.

## Changelog

### Version 2.0.0 (Current)
- Complete rewrite for Python 3.8+
- Added type annotations throughout
- Proper context managers for file handling
- Dataclasses for structured data
- Improved error handling
- Better API with clear method names
- Comprehensive test suite
- Enhanced documentation

### Version 1.0.0 (Original)
- Initial Python 2.x version
- Basic WMA/WMV parsing functionality
