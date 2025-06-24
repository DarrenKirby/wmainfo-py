"""Type stubs for wmainfo module."""

from pathlib import Path
from typing import Dict, Optional, Union, Any


class WmaInfoError(Exception):
    """Exception raised for WMA parsing errors."""
    ...


class ASFObject:
    """Represents an ASF object with its properties."""
    guid: str
    size: int
    offset: int
    name: Optional[str]

    def __init__(
            self,
            guid: str,
            size: int,
            offset: int,
            name: Optional[str] = None
    ) -> None: ...


class StreamInfo:
    """Container for stream properties."""
    stream_type_guid: str
    stream_type_name: str
    error_correct_guid: str
    error_correct_name: str
    time_offset: int
    type_data_length: int
    error_data_length: int
    stream_number: int
    encrypted: bool
    type_specific_data: bytes
    error_correct_data: bytes
    audio_channels: Optional[int]
    audio_sample_rate: Optional[int]
    audio_bitrate: Optional[int]
    audio_bits_per_sample: Optional[int]


class WmaInfo:
    """WMA/WMV file metadata parser."""

    file_path: Path
    debug: bool
    drm: bool
    tags: Dict[str, Any]
    info: Dict[str, Any]
    header_objects: Dict[str, ASFObject]
    stream: Optional[StreamInfo]

    def __init__(
            self,
            file_path: Union[str, Path],
            debug: bool = False
    ) -> None: ...

    def has_drm(self) -> bool: ...

    def has_tag(self, tag: str) -> bool: ...

    def has_info(self, field: str) -> bool: ...

    def print_objects(self) -> None: ...

    def print_tags(self) -> None: ...

    def print_info(self) -> None: ...

    def parse_stream(self) -> None: ...


def main() -> None: ...
