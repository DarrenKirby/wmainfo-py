#!/usr/bin/env python3
"""
Unit tests for the modernized WMA info parser.
"""

import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from typing import Optional

from wmainfo import WmaInfo, WmaInfoError, ASFObject, StreamInfo


class TestWmaInfo(unittest.TestCase):
    """Test cases for WmaInfo class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create a minimal valid ASF header for testing
        self.valid_header = (
            # ASF Header Object GUID (75B22630-668E-11CF-A6D9-00AA0062CE6C)
            b'\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c'
            # Object size (8 bytes, little-endian) - 130 bytes
            b'\x82\x00\x00\x00\x00\x00\x00\x00'
            # Number of header objects (4 bytes) - 0 objects
            b'\x00\x00\x00\x00'
            # Reserved (2 bytes)
            b'\x01\x02'
        )

        # Path for test file
        self.test_file = Path(tempfile.mktemp(suffix='.wma'))

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        if self.test_file.exists():
            self.test_file.unlink()

    def test_init_with_valid_file(self) -> None:
        """Test initialization with a valid file."""
        # Write minimal header to test file
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)

        wma = WmaInfo(self.test_file)

        self.assertIsInstance(wma.tags, dict)
        self.assertIsInstance(wma.info, dict)
        self.assertIsInstance(wma.header_objects, dict)
        self.assertFalse(wma.drm)
        self.assertIn('ASF_Header_Object', wma.header_objects)

    def test_init_with_invalid_file(self) -> None:
        """Test initialization with an invalid file."""
        # Write invalid data to test file
        self.test_file.write_bytes(b'INVALID' * 10)

        with self.assertRaises(WmaInfoError):
            WmaInfo(self.test_file)

    def test_init_with_nonexistent_file(self) -> None:
        """Test initialization with a non-existent file."""
        with self.assertRaises(FileNotFoundError):
            WmaInfo('/nonexistent/file.wma')

    def test_has_drm_false_by_default(self) -> None:
        """Test that DRM is false by default."""
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)
        wma = WmaInfo(self.test_file)

        self.assertFalse(wma.has_drm())

    def test_has_tag(self) -> None:
        """Test has_tag method."""
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)
        wma = WmaInfo(self.test_file)

        # Add test tags
        wma.tags['Title'] = 'Test Song'
        wma.tags['Author'] = ''

        self.assertTrue(wma.has_tag('Title'))
        self.assertFalse(wma.has_tag('Author'))  # Empty string
        self.assertFalse(wma.has_tag('NonExistent'))

    def test_has_info(self) -> None:
        """Test has_info method."""
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)
        wma = WmaInfo(self.test_file)

        # Add test info
        wma.info['bitrate'] = 128
        wma.info['empty'] = ''

        self.assertTrue(wma.has_info('bitrate'))
        self.assertFalse(wma.has_info('empty'))  # Empty string
        self.assertFalse(wma.has_info('NonExistent'))

    def test_byte_string_to_guid(self) -> None:
        """Test GUID conversion."""
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)
        wma = WmaInfo(self.test_file)

        # Test with known GUID bytes
        guid_bytes = b'\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c'
        expected = '75B22630-668E-11CF-A6D9-00AA0062CE6C'

        result = wma._byte_string_to_guid(guid_bytes)
        self.assertEqual(result, expected)

    def test_byte_string_to_guid_invalid_length(self) -> None:
        """Test GUID conversion with invalid byte length."""
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)
        wma = WmaInfo(self.test_file)

        with self.assertRaises(ValueError):
            wma._byte_string_to_guid(b'TOO SHORT')

    def test_parse_64bit_string(self) -> None:
        """Test 64-bit integer parsing."""
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)
        wma = WmaInfo(self.test_file)

        # Test with known value
        data = b'\x00\x01\x02\x03\x04\x05\x06\x07'
        result = wma._parse_64bit_string(data)

        # Should parse as little-endian
        expected = 0x0706050403020100
        self.assertEqual(result, expected)

    def test_file_time_to_unix_time(self) -> None:
        """Test Windows FILETIME to Unix timestamp conversion."""
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)
        wma = WmaInfo(self.test_file)

        # Windows FILETIME for Unix epoch (Jan 1, 1970)
        filetime = 116_444_736_000_000_000
        result = wma._file_time_to_unix_time(filetime)
        self.assertEqual(result, 0)

        # Test with a known date
        # Jan 1, 2000 00:00:00 UTC
        filetime = 125_911_584_000_000_000
        result = wma._file_time_to_unix_time(filetime)
        expected = 946_684_800  # Unix timestamp for Jan 1, 2000
        self.assertEqual(result, expected)

    def test_decode_binary_string(self) -> None:
        """Test UTF-16LE string decoding."""
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)
        wma = WmaInfo(self.test_file)

        # Test with valid UTF-16LE string
        data = 'Hello'.encode('utf-16le') + b'\x00\x00'
        result = wma._decode_binary_string(data)
        self.assertEqual(result, 'Hello')

        # Test with empty string
        result = wma._decode_binary_string(b'')
        self.assertEqual(result, '')

        # Test with null terminators
        data = 'Test\x00'.encode('utf-16le')
        result = wma._decode_binary_string(data)
        self.assertEqual(result, 'Test')

    def test_print_methods_dont_crash(self) -> None:
        """Test that print methods don't raise exceptions."""
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)
        wma = WmaInfo(self.test_file)

        # Add some test data
        wma.tags['Title'] = 'Test'
        wma.info['bitrate'] = 128

        # These should not raise
        wma.print_tags()
        wma.print_info()
        wma.print_objects()

    def test_parse_stream_without_stream_object(self) -> None:
        """Test parse_stream when no stream object exists."""
        self.test_file.write_bytes(self.valid_header + b'\x00' * 100)
        wma = WmaInfo(self.test_file)

        with self.assertRaises(WmaInfoError):
            wma.parse_stream()


class TestASFObject(unittest.TestCase):
    """Test cases for ASFObject dataclass."""

    def test_creation(self) -> None:
        """Test ASFObject creation."""
        obj = ASFObject(
            guid='75B22630-668E-11CF-A6D9-00AA0062CE6C',
            size=130,
            offset=0,
            name='ASF_Header_Object'
        )

        self.assertEqual(obj.guid, '75B22630-668E-11CF-A6D9-00AA0062CE6C')
        self.assertEqual(obj.size, 130)
        self.assertEqual(obj.offset, 0)
        self.assertEqual(obj.name, 'ASF_Header_Object')

    def test_repr(self) -> None:
        """Test ASFObject string representation."""
        obj = ASFObject(
            guid='TEST-GUID',
            size=100,
            offset=50,
            name='Test Object'
        )

        repr_str = repr(obj)
        self.assertIn('Test Object', repr_str)
        self.assertIn('TEST-GUID', repr_str)
        self.assertIn('100', repr_str)
        self.assertIn('50', repr_str)


class TestStreamInfo(unittest.TestCase):
    """Test cases for StreamInfo dataclass."""

    def test_default_values(self) -> None:
        """Test StreamInfo default values."""
        stream = StreamInfo()

        self.assertEqual(stream.stream_type_guid, "")
        self.assertEqual(stream.stream_type_name, "")
        self.assertEqual(stream.time_offset, 0)
        self.assertEqual(stream.stream_number, 0)
        self.assertFalse(stream.encrypted)
        self.assertIsNone(stream.audio_channels)
        self.assertIsNone(stream.audio_sample_rate)


class TestWmaInfoError(unittest.TestCase):
    """Test cases for WmaInfoError exception."""

    def test_exception_message(self) -> None:
        """Test exception message."""
        error = WmaInfoError("Test error message")
        self.assertEqual(str(error), "Test error message")

    def test_exception_inheritance(self) -> None:
        """Test that WmaInfoError inherits from Exception."""
        self.assertTrue(issubclass(WmaInfoError, Exception))


if __name__ == '__main__':
    unittest.main()
