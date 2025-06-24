#!/usr/bin/env python3
"""
Example usage of the modernized wmainfo library.
"""

from pathlib import Path
from typing import Optional
import sys

from wmainfo import WmaInfo, WmaInfoError


def format_duration(seconds: int) -> str:
    """Format duration in seconds to a readable string."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def format_size(bytes_size: int) -> str:
    """Format file size to a readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def analyze_media_file(file_path: Path) -> None:
    """
    Analyze a WMA/WMV file and display its metadata.

    Args:
        file_path: Path to the media file
    """
    print(f"\n{'=' * 60}")
    print(f"Analyzing: {file_path.name}")
    print(f"{'=' * 60}\n")

    try:
        # Parse the file
        wma = WmaInfo(file_path)

        # Display basic file information
        print("📁 File Information:")
        print("-" * 40)

        if 'filesize' in wma.info:
            print(f"Size:         {format_size(wma.info['filesize'])}")

        if 'playtime_seconds' in wma.info:
            print(f"Duration:     {format_duration(wma.info['playtime_seconds'])}")

        if 'bitrate' in wma.info:
            print(f"Bitrate:      {wma.info['bitrate']:.0f} kbps")

        if 'creation_string' in wma.info:
            print(f"Created:      {wma.info['creation_string']}")

        if 'seekable' in wma.info:
            seekable = "Yes" if wma.info['seekable'] else "No"
            print(f"Seekable:     {seekable}")

        if 'broadcast' in wma.info:
            streamable = "Yes" if wma.info['broadcast'] else "No"
            print(f"Streamable:   {streamable}")

        # Display metadata tags
        if wma.tags:
            print("\n🎵 Metadata Tags:")
            print("-" * 40)

            # Common tags in preferred order
            tag_order = [
                'Title', 'Author', 'AlbumTitle', 'AlbumArtist',
                'TrackNumber', 'Genre', 'Year', 'Composer',
                'Copyright', 'Description', 'Rating'
            ]

            # Display tags in order
            for tag in tag_order:
                if wma.has_tag(tag):
                    print(f"{tag:13} {wma.tags[tag]}")

            # Display any remaining tags
            for tag, value in wma.tags.items():
                if tag not in tag_order and value:
                    print(f"{tag:13} {value}")

        # Parse and display stream information
        try:
            wma.parse_stream()
            if wma.stream and wma.stream.stream_type_name:
                print("\n🎬 Stream Properties:")
                print("-" * 40)
                print(f"Stream Type:  {wma.stream.stream_type_name}")

                if wma.stream.audio_channels:
                    channels = "Mono" if wma.stream.audio_channels == 1 else "Stereo"
                    if wma.stream.audio_channels > 2:
                        channels = f"{wma.stream.audio_channels} channels"
                    print(f"Channels:     {channels}")

                if wma.stream.audio_sample_rate:
                    print(f"Sample Rate:  {wma.stream.audio_sample_rate} Hz")

                if wma.stream.audio_bitrate:
                    print(f"Audio Bitrate: {wma.stream.audio_bitrate} bps")

                if wma.stream.audio_bits_per_sample:
                    print(f"Bit Depth:    {wma.stream.audio_bits_per_sample} bits")

                if wma.stream.encrypted:
                    print(f"Encrypted:    Yes")
        except WmaInfoError:
            # Stream parsing is optional
            pass

        # Display DRM status
        if wma.has_drm():
            print("\n⚠️  DRM Protection: ENABLED")
            print("This file is protected by Digital Rights Management")

        # Display ASF objects summary
        print(f"\n📦 ASF Objects: {len(wma.header_objects)}")
        print("-" * 40)

        total_size = sum(obj.size for obj in wma.header_objects.values())
        print(f"Total header size: {format_size(total_size)}")

        # Show largest objects
        sorted_objects = sorted(
            wma.header_objects.items(),
            key=lambda x: x[1].size,
            reverse=True
        )[:5]

        print("\nLargest objects:")
        for name, obj in sorted_objects:
            size_pct = (obj.size / total_size) * 100
            print(f"  {name}: {format_size(obj.size)} ({size_pct:.1f}%)")

    except WmaInfoError as e:
        print(f"❌ Error: {e}")
    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}")
    except PermissionError:
        print(f"❌ Error: Permission denied: {file_path}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python example.py <media_file.wma|wmv> [...]")
        sys.exit(1)

    # Process each file
    for file_arg in sys.argv[1:]:
        file_path = Path(file_arg)

        if file_path.is_file():
            analyze_media_file(file_path)
        elif file_path.is_dir():
            print(f"\n📂 Processing directory: {file_path}")

            # Find all WMA/WMV files
            media_files = list(file_path.rglob("*.wm[av]"))

            if not media_files:
                print(f"No WMA/WMV files found in {file_path}")
            else:
                print(f"Found {len(media_files)} media files")
                for media_file in sorted(media_files):
                    analyze_media_file(media_file)
        else:
            print(f"❌ Not found: {file_path}")

    print(f"\n{'=' * 60}")
    print("Analysis complete")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
