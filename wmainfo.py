#!/usr/bin/env python3
"""
WMA/WMV metadata parser for Python 3.8+

Description:
    wmainfo-py provides access to low-level information on WMA/WMV files.
    * Identifies all ASF objects and shows each object's size
    * Returns info such as bitrate, size, length, creation date, etc.
    * Returns meta-tags from ASF_Content_Description_Object

Note:
    Originally based on Dan Sully's Audio-WMA Perl module
    (http://cpants.perl.org/dist/Audio-WMA :: http://www.slimdevices.com/)
    Modernized for Python 3.8+ with type annotations and best practices.

License: Artistic/Perl
"""

import re
import time
from dataclasses import dataclass
from pathlib import Path
import struct
from struct import unpack
from typing import Dict, Optional, Union, BinaryIO, Any


class WmaInfoError(Exception):
    """Exception raised for WMA parsing errors."""
    pass


@dataclass
class ASFObject:
    """Represents an ASF object with its properties."""
    guid: str
    size: int
    offset: int
    name: Optional[str] = None

    def __repr__(self) -> str:
        return f"ASFObject(name={self.name}, guid={self.guid}, size={self.size}, offset={self.offset})"


@dataclass
class StreamInfo:
    """Container for stream properties."""
    stream_type_guid: str = ""
    stream_type_name: str = ""
    error_correct_guid: str = ""
    error_correct_name: str = ""
    time_offset: int = 0
    type_data_length: int = 0
    error_data_length: int = 0
    stream_number: int = 0
    encrypted: bool = False
    type_specific_data: bytes = b""
    error_correct_data: bytes = b""
    # Audio specific
    audio_channels: Optional[int] = None
    audio_sample_rate: Optional[int] = None
    audio_bitrate: Optional[int] = None
    audio_bits_per_sample: Optional[int] = None


class WmaInfo:
    """
    WMA/WMV file metadata parser.

    Attributes:
        file_path: Path to the WMA/WMV file
        drm: Whether the file has DRM protection
        tags: Dictionary of ID3-like metadata tags
        info: Dictionary of non-ID3 file information
        header_objects: Dictionary of ASF header objects
        stream: Stream properties (populated via parse_stream())
    """

    def __init__(self, file_path: Union[str, Path], debug: bool = False) -> None:
        """
        Initialize WMA parser and parse the file header.

        Args:
            file_path: Path to the WMA/WMV file
            debug: Enable debug output

        Raises:
            WmaInfoError: If file cannot be parsed
        """
        self.file_path = Path(file_path)
        self.debug = debug

        # Public attributes
        self.drm: bool = False
        self.tags: Dict[str, Any] = {}
        self.info: Dict[str, Any] = {}
        self.header_objects: Dict[str, ASFObject] = {}
        self.stream: Optional[StreamInfo] = None

        # Private attributes
        self._size: int = 0
        self._offset: int = 0
        self._file_offset: int = 30
        self._header_data: bytes = b""
        self._guid_mapping: Dict[str, str] = self._get_known_guids()
        self._reverse_guid_mapping: Dict[str, str] = {v: k for k, v in self._guid_mapping.items()}

        self._parse_wma_header()

    def __repr__(self) -> str:
        return f"WmaInfo(file_path={self.file_path}, tags={len(self.tags)}, info={len(self.info)})"

    def has_drm(self) -> bool:
        """Check if the file has DRM protection."""
        return self.drm

    def has_tag(self, tag: str) -> bool:
        """
        Check if a specific tag exists and has a value.

        Args:
            tag: Tag name to check

        Returns:
            True if tag exists and is not empty
        """
        return tag in self.tags and self.tags[tag] != ""

    def has_info(self, field: str) -> bool:
        """
        Check if a specific info field exists and has a value.

        Args:
            field: Field name to check

        Returns:
            True if field exists and is not empty
        """
        return field in self.info and self.info[field] != ""

    def print_objects(self) -> None:
        """
        Print all ASF objects.

        ASF_Header_Object prints: "name: GUID size num_objects"
        All other objects print: "name: GUID size offset"
        """
        for name, obj in self.header_objects.items():
            if hasattr(obj, 'num_objects'):
                print(f"{name}: {obj.guid} {obj.size} {obj.num_objects}")
            else:
                print(f"{name}: {obj.guid} {obj.size} {obj.offset}")

    def print_tags(self) -> None:
        """
        Print all ID3-like metadata tags.

        This includes data from:
        - ASF_Content_Description_Object
        - ASF_Extended_Content_Description_Object
        """
        max_key_len = max(len(k) for k in self.tags.keys()) if self.tags else 0
        for key, value in self.tags.items():
            padding = max_key_len - len(key) + 2
            print(f"{key}:{' ' * padding}{value}")

    def print_info(self) -> None:
        """
        Print all non-ID3 file information.

        This includes data from:
        - ASF_File_Properties_Object
        - ASF_Extended_Content_Description_Object
        """
        max_key_len = max(len(k) for k in self.info.keys()) if self.info else 0
        for key, value in self.info.items():
            padding = max_key_len - len(key) + 2
            print(f"{key}:{' ' * padding}{value}")

    def parse_stream(self) -> None:
        """
        Parse stream properties.

        Note: Most users won't need this information, so it's not parsed automatically.

        Raises:
            WmaInfoError: If ASF_Stream_Properties_Object cannot be parsed
        """
        try:
            if 'ASF_Stream_Properties_Object' not in self.header_objects:
                raise WmaInfoError("No ASF_Stream_Properties_Object found")

            offset = self.header_objects['ASF_Stream_Properties_Object'].offset
            self._parse_asf_stream_properties_object(offset)
        except Exception as e:
            raise WmaInfoError(f"Cannot parse ASF_Stream_Properties_Object: {e}")

    def _parse_wma_header(self) -> None:
        """Parse the WMA file header."""
        self._size = self.file_path.stat().st_size

        with open(self.file_path, 'rb') as fh:
            self._parse_header_object(fh)
            self._header_data = fh.read(self.header_objects['ASF_Header_Object'].size - 30)

        self._parse_header_contents()

    def _parse_header_object(self, fh: BinaryIO) -> None:
        """Parse the main ASF header object."""
        try:
            object_id = self._byte_string_to_guid(fh.read(16))
            object_size = unpack("<Q", fh.read(8))[0]
            header_objects = unpack("<I", fh.read(4))[0]
            reserved1 = unpack("b", fh.read(1))[0]
            reserved2 = unpack("b", fh.read(1))[0]
            object_id_name = self._reverse_guid_mapping.get(object_id)

            if not object_id_name:
                raise WmaInfoError(f"Unknown GUID: {object_id}")

        except (struct.error, KeyError) as e:
            raise WmaInfoError(f"{self.file_path} doesn't appear to have a valid ASF header: {e}")

        if object_size > self._size:
            raise WmaInfoError("Header size reported larger than file size")

        # Store header object with additional attributes
        header_obj = ASFObject(
            guid=object_id,
            size=object_size,
            offset=0,
            name=object_id_name
        )
        # Add extra attributes for header object
        header_obj.num_objects = header_objects
        header_obj.reserved1 = reserved1
        header_obj.reserved2 = reserved2

        self.header_objects[object_id_name] = header_obj

        if self.debug:
            print(f"objectId:      {object_id}")
            print(f"objectIdName:  {object_id_name}")
            print(f"objectSize:    {object_size}")
            print(f"headerObjects: {header_objects}")
            print(f"reserved1:     {reserved1}")
            print(f"reserved2:     {reserved2}")

    def _parse_header_contents(self) -> None:
        """Parse the contents of the header object."""
        header_obj = self.header_objects['ASF_Header_Object']

        for _ in range(header_obj.num_objects):
            next_object = self._read_and_increment_offset(16)
            next_object_text = self._byte_string_to_guid(next_object)
            next_object_size = self._parse_64bit_string(self._read_and_increment_offset(8))
            next_object_name = self._reverse_guid_mapping.get(next_object_text, "Unknown")

            self.header_objects[next_object_name] = ASFObject(
                guid=next_object_text,
                size=next_object_size,
                offset=self._file_offset,
                name=next_object_name
            )
            self._file_offset += next_object_size

            if self.debug:
                print(f"nextObjectGUID: {next_object_text}")
                print(f"nextObjectName: {next_object_name}")
                print(f"nextObjectSize: {next_object_size}")

            # Parse specific object contents
            if next_object_name == 'ASF_File_Properties_Object':
                self._parse_asf_file_properties_object()
            elif next_object_name == 'ASF_Content_Description_Object':
                self._parse_asf_content_description_object()
            elif next_object_name == 'ASF_Extended_Content_Description_Object':
                self._parse_asf_extended_content_description_object()
            elif next_object_name in ('ASF_Content_Encryption_Object',
                                      'ASF_Extended_Content_Encryption_Object'):
                self.drm = True
            else:
                # Skip unknown object content
                self._offset += next_object_size - 24

    def _parse_asf_file_properties_object(self) -> None:
        """Parse ASF File Properties Object."""
        file_id = self._read_and_increment_offset(16)
        self.info['fileid_guid'] = self._byte_string_to_guid(file_id)
        self.info['filesize'] = int(self._parse_64bit_string(self._read_and_increment_offset(8)))
        self.info['creation_date'] = unpack("<Q", self._read_and_increment_offset(8))[0]
        self.info['creation_date_unix'] = self._file_time_to_unix_time(self.info['creation_date'])
        self.info['creation_string'] = time.strftime("%c", time.gmtime(self.info['creation_date_unix']))
        self.info['data_packets'] = unpack("<Q", self._read_and_increment_offset(8))[0]
        self.info['play_duration'] = self._parse_64bit_string(self._read_and_increment_offset(8))
        self.info['send_duration'] = self._parse_64bit_string(self._read_and_increment_offset(8))
        self.info['preroll'] = unpack("<Q", self._read_and_increment_offset(8))[0]
        self.info['playtime_seconds'] = int(
            self.info['play_duration'] / 10_000_000 - self.info['preroll'] / 1000
        )

        flags_raw = unpack("<I", self._read_and_increment_offset(4))[0]
        self.info['broadcast'] = bool(flags_raw & 0x0001)
        self.info['seekable'] = bool(flags_raw & 0x0002)

        self.info['min_packet_size'] = unpack("<I", self._read_and_increment_offset(4))[0]
        self.info['max_packet_size'] = unpack("<I", self._read_and_increment_offset(4))[0]
        self.info['max_bitrate'] = unpack("<I", self._read_and_increment_offset(4))[0]
        self.info['bitrate'] = self.info['max_bitrate'] / 1000

        if self.debug:
            for key, val in self.info.items():
                print(f"{key}: {val}")

    def _parse_asf_content_description_object(self) -> None:
        """Parse ASF Content Description Object."""
        lengths = {}
        keys = ["Title", "Author", "Copyright", "Description", "Rating"]

        # Read the lengths of each key
        for key in keys:
            lengths[key] = unpack("<H", self._read_and_increment_offset(2))[0]

        # Read the data based on length
        for key in keys:
            if lengths[key] > 0:
                self.tags[key] = self._decode_binary_string(
                    self._read_and_increment_offset(lengths[key])
                )

    def _parse_asf_extended_content_description_object(self) -> None:
        """Parse ASF Extended Content Description Object."""
        ext_info = {}
        content_count = unpack("<H", self._read_and_increment_offset(2))[0]

        for _ in range(content_count):
            ext = {}
            ext['base_offset'] = self._offset + 30
            ext['name_length'] = unpack("<H", self._read_and_increment_offset(2))[0]
            ext['name'] = self._decode_binary_string(
                self._read_and_increment_offset(ext['name_length'])
            )
            ext['value_type'] = unpack("<H", self._read_and_increment_offset(2))[0]
            ext['value_length'] = unpack("<H", self._read_and_increment_offset(2))[0]

            value = self._read_and_increment_offset(ext['value_length'])

            # Parse value based on type
            if ext['value_type'] <= 1:  # Unicode string
                ext['value'] = self._decode_binary_string(value)
            elif ext['value_type'] == 2:  # Boolean
                ext['value'] = unpack("<I", value)[0] != 0
            elif ext['value_type'] == 3:  # DWORD
                ext['value'] = unpack("<I", value)[0]
            elif ext['value_type'] == 4:  # QWORD
                ext['value'] = self._parse_64bit_string(value)
            elif ext['value_type'] == 5:  # WORD
                ext['value'] = unpack("<H", value)[0]
            else:
                ext['value'] = value  # Raw bytes for unknown types

            if self.debug:
                print(f"base_offset:  {ext['base_offset']}")
                print(f"name length:  {ext['name_length']}")
                print(f"name:         {ext['name']}")
                print(f"value type:   {ext['value_type']}")
                print(f"value length: {ext['value_length']}")
                print(f"value:        {ext['value']}")

            ext_info[ext['name']] = ext['value']

        # Sort and dispatch info
        tag_pattern = re.compile(
            r"(TrackNumber|AlbumTitle|AlbumArtist|Genre|Year|Composer|"
            r"Mood|Lyrics|BeatsPerMinute)"
        )

        for key, value in ext_info.items():
            clean_key = key.replace("WM/", "")
            if tag_pattern.search(key):
                self.tags[clean_key] = value
            else:
                self.info[clean_key] = value

    def _parse_asf_stream_properties_object(self, offset: int) -> None:
        """Parse ASF Stream Properties Object."""
        self._offset = offset - 30  # Adjust offset
        self.stream = StreamInfo()

        stream_type = self._read_and_increment_offset(16)
        self.stream.stream_type_guid = self._byte_string_to_guid(stream_type)
        self.stream.stream_type_name = self._reverse_guid_mapping.get(
            self.stream.stream_type_guid, "Unknown"
        )

        error_type = self._read_and_increment_offset(16)
        self.stream.error_correct_guid = self._byte_string_to_guid(error_type)
        self.stream.error_correct_name = self._reverse_guid_mapping.get(
            self.stream.error_correct_guid, "Unknown"
        )

        self.stream.time_offset = unpack("<Q", self._read_and_increment_offset(8))[0]
        self.stream.type_data_length = unpack("<I", self._read_and_increment_offset(4))[0]
        self.stream.error_data_length = unpack("<I", self._read_and_increment_offset(4))[0]

        flags_raw = unpack("<H", self._read_and_increment_offset(2))[0]
        self.stream.stream_number = flags_raw & 0x007F
        self.stream.encrypted = bool(flags_raw & 0x8000)

        # Skip reserved field
        self._read_and_increment_offset(4)

        self.stream.type_specific_data = self._read_and_increment_offset(
            self.stream.type_data_length
        )
        self.stream.error_correct_data = self._read_and_increment_offset(
            self.stream.error_data_length
        )

        if self.stream.stream_type_name == 'ASF_Audio_Media':
            self._parse_asf_audio_media_object()

    def _parse_asf_audio_media_object(self) -> None:
        """Parse ASF Audio Media Object."""
        if not self.stream or not self.stream.type_specific_data:
            return

        data = self.stream.type_specific_data[:16]
        if len(data) >= 16:
            self.stream.audio_channels = unpack("<H", data[2:4])[0]
            self.stream.audio_sample_rate = unpack("<I", data[4:8])[0]
            self.stream.audio_bitrate = unpack("<I", data[8:12])[0] * 8
            self.stream.audio_bits_per_sample = unpack("<H", data[14:16])[0]

    @staticmethod
    def _decode_binary_string(data: bytes) -> str:
        """Decode a UTF-16LE binary string."""
        try:
            return data.decode('utf-16le', 'ignore').rstrip('\x00')
        except UnicodeDecodeError:
            return ""

    def _read_and_increment_offset(self, size: int) -> bytes:
        """Read data from header and increment offset."""
        value = self._header_data[self._offset:self._offset + size]
        self._offset += size
        return value

    @staticmethod
    def _byte_string_to_guid(byte_string: bytes) -> str:
        """Convert a 16-byte string to GUID format."""
        if len(byte_string) != 16:
            raise ValueError(f"Invalid GUID byte string length: {len(byte_string)}")

        b = unpack("16B", byte_string)

        guid = (
            f"{b[3]:02X}{b[2]:02X}{b[1]:02X}{b[0]:02X}-"
            f"{b[5]:02X}{b[4]:02X}-"
            f"{b[7]:02X}{b[6]:02X}-"
            f"{b[8]:02X}{b[9]:02X}-"
            f"{b[10]:02X}{b[11]:02X}{b[12]:02X}{b[13]:02X}{b[14]:02X}{b[15]:02X}"
        )

        return guid

    @staticmethod
    def _parse_64bit_string(data: bytes) -> int:
        """Parse a 64-bit little-endian integer."""
        return unpack('<Q', data)[0]

    @staticmethod
    def _file_time_to_unix_time(file_time: int) -> int:
        """Convert Windows FILETIME to Unix timestamp."""
        # Windows FILETIME is 100-nanosecond intervals since January 1, 1601
        return int((file_time - 116_444_736_000_000_000) / 10_000_000)

    @staticmethod
    def _get_known_guids() -> Dict[str, str]:
        """Return dictionary of known ASF GUIDs."""
        return {
            'ASF_Extended_Stream_Properties_Object': '14E6A5CB-C672-4332-8399-A96952065B5A',
            'ASF_Padding_Object': '1806D474-CADF-4509-A4BA-9AABCB96AAE8',
            'ASF_Payload_Ext_Syst_Pixel_Aspect_Ratio': '1B1EE554-F9EA-4BC8-821A-376B74E4C4B8',
            'ASF_Script_Command_Object': '1EFB1A30-0B62-11D0-A39B-00A0C90348F6',
            'ASF_No_Error_Correction': '20FB5700-5B55-11CF-A8FD-00805F5C442B',
            'ASF_Content_Branding_Object': '2211B3FA-BD23-11D2-B4B7-00A0C955FC6E',
            'ASF_Content_Encryption_Object': '2211B3FB-BD23-11D2-B4B7-00A0C955FC6E',
            'ASF_Digital_Signature_Object': '2211B3FC-BD23-11D2-B4B7-00A0C955FC6E',
            'ASF_Extended_Content_Encryption_Object': '298AE614-2622-4C17-B935-DAE07EE9289C',
            'ASF_Simple_Index_Object': '33000890-E5B1-11CF-89F4-00A0C90349CB',
            'ASF_Degradable_JPEG_Media': '35907DE0-E415-11CF-A917-00805F5C442B',
            'ASF_Payload_Extension_System_Timecode': '399595EC-8667-4E2D-8FDB-98814CE76C1E',
            'ASF_Binary_Media': '3AFB65E2-47EF-40F2-AC2C-70A90D71D343',
            'ASF_Timecode_Index_Object': '3CB73FD0-0C4A-4803-953D-EDF7B6228F0C',
            'ASF_Metadata_Library_Object': '44231C94-9498-49D1-A141-1D134E457054',
            'ASF_Reserved_3': '4B1ACBE3-100B-11D0-A39B-00A0C90348F6',
            'ASF_Reserved_4': '4CFEDB20-75F6-11CF-9C0F-00A0C90349CB',
            'ASF_Command_Media': '59DACFC0-59E6-11D0-A3AC-00A0C90348F6',
            'ASF_Header_Extension_Object': '5FBF03B5-A92E-11CF-8EE3-00C00C205365',
            'ASF_Media_Object_Index_Parameters_Obj': '6B203BAD-3F11-4E84-ACA8-D7613DE2CFA7',
            'ASF_Header_Object': '75B22630-668E-11CF-A6D9-00AA0062CE6C',
            'ASF_Content_Description_Object': '75B22633-668E-11CF-A6D9-00AA0062CE6C',
            'ASF_Error_Correction_Object': '75B22635-668E-11CF-A6D9-00AA0062CE6C',
            'ASF_Data_Object': '75B22636-668E-11CF-A6D9-00AA0062CE6C',
            'ASF_Web_Stream_Media_Subtype': '776257D4-C627-41CB-8F81-7AC7FF1C40CC',
            'ASF_Stream_Bitrate_Properties_Object': '7BF875CE-468D-11D1-8D82-006097C9A2B2',
            'ASF_Language_List_Object': '7C4346A9-EFE0-4BFC-B229-393EDE415C85',
            'ASF_Codec_List_Object': '86D15240-311D-11D0-A3A4-00A0C90348F6',
            'ASF_Reserved_2': '86D15241-311D-11D0-A3A4-00A0C90348F6',
            'ASF_File_Properties_Object': '8CABDCA1-A947-11CF-8EE4-00C00C205365',
            'ASF_File_Transfer_Media': '91BD222C-F21C-497A-8B6D-5AA86BFC0185',
            'ASF_Advanced_Mutual_Exclusion_Object': 'A08649CF-4775-4670-8A16-6E35357566CD',
            'ASF_Bandwidth_Sharing_Object': 'A69609E6-517B-11D2-B6AF-00C04FD908E9',
            'ASF_Reserved_1': 'ABD3D211-A9BA-11CF-8EE6-00C00C205365',
            'ASF_Bandwidth_Sharing_Exclusive': 'AF6060AA-5197-11D2-B6AF-00C04FD908E9',
            'ASF_Bandwidth_Sharing_Partial': 'AF6060AB-5197-11D2-B6AF-00C04FD908E9',
            'ASF_JFIF_Media': 'B61BE100-5B4E-11CF-A8FD-00805F5C442B',
            'ASF_Stream_Properties_Object': 'B7DC0791-A9B7-11CF-8EE6-00C00C205365',
            'ASF_Video_Media': 'BC19EFC0-5B4D-11CF-A8FD-00805F5C442B',
            'ASF_Audio_Spread': 'BFC3CD50-618F-11CF-8BB2-00AA00B4E220',
            'ASF_Metadata_Object': 'C5F8CBEA-5BAF-4877-8467-AA8C44FA4CCA',
            'ASF_Payload_Ext_Syst_Sample_Duration': 'C6BD9450-867F-4907-83A3-C77921B733AD',
            'ASF_Group_Mutual_Exclusion_Object': 'D1465A40-5A79-4338-B71B-E36B8FD6C249',
            'ASF_Extended_Content_Description_Object': 'D2D0A440-E307-11D2-97F0-00A0C95EA850',
            'ASF_Stream_Prioritization_Object': 'D4FED15B-88D3-454F-81F0-ED5C45999E24',
            'ASF_Payload_Ext_System_Content_Type': 'D590DC20-07BC-436C-9CF7-F3BBFBF1A4DC',
            'ASF_Index_Object': 'D6E229D3-35DA-11D1-9034-00A0C90349BE',
            'ASF_Bitrate_Mutual_Exclusion_Object': 'D6E229DC-35DA-11D1-9034-00A0C90349BE',
            'ASF_Index_Parameters_Object': 'D6E229DF-35DA-11D1-9034-00A0C90349BE',
            'ASF_Mutex_Language': 'D6E22A00-35DA-11D1-9034-00A0C90349BE',
            'ASF_Mutex_Bitrate': 'D6E22A01-35DA-11D1-9034-00A0C90349BE',
            'ASF_Mutex_Unknown': 'D6E22A02-35DA-11D1-9034-00A0C90349BE',
            'ASF_Web_Stream_Format': 'DA1E6B13-8359-4050-B398-388E965BF00C',
            'ASF_Payload_Ext_System_File_Name': 'E165EC0E-19ED-45D7-B4A7-25CBD1E28E9B',
            'ASF_Marker_Object': 'F487CD01-A951-11CF-8EE6-00C00C205365',
            'ASF_Timecode_Index_Parameters_Object': 'F55E496D-9797-4B5D-8C8B-604DFE9BFB24',
            'ASF_Audio_Media': 'F8699E40-5B4D-11CF-A8FD-00805F5C442B',
            'ASF_Media_Object_Index_Object': 'FEB103F8-12AD-4C64-840F-2A1D2F7AD48C',
            'ASF_Alt_Extended_Content_Encryption_Obj': 'FF889EF1-ADEE-40DA-9E71-98704BB928CE',
        }


def main():
    """Command-line interface for WMA info."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Parse WMA/WMV file metadata')
    parser.add_argument('file', help='Path to WMA/WMV file')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--no-info', action='store_true', help='Skip file info output')
    parser.add_argument('--no-tags', action='store_true', help='Skip tags output')
    parser.add_argument('--no-objects', action='store_true', help='Skip objects output')
    parser.add_argument('--stream', action='store_true', help='Parse and show stream info')

    args = parser.parse_args()

    try:
        wma = WmaInfo(args.file, debug=args.debug)

        if not args.no_info:
            print("### Info ###\n")
            wma.print_info()
            print()

        if not args.no_tags:
            print("### Tags ###\n")
            wma.print_tags()
            print()

        if not args.no_objects:
            print("### Objects ###\n")
            wma.print_objects()
            print()

        if args.stream:
            print("### Stream ###\n")
            wma.parse_stream()
            if wma.stream:
                for attr, value in vars(wma.stream).items():
                    if value is not None and not attr.startswith('_'):
                        print(f"{attr}: {value}")
            print()

        if wma.has_drm():
            print("WARNING: This file has DRM protection")

    except WmaInfoError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
