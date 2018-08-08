"""Inteded to be used with vim's selected text filter command to convert xxd output
to parsed structures/bitfields."""

import re
import struct
import unittest
import sys


def ParseHexdump(xxd_str):
  raw_bytes = b''

  lines = xxd_str.split('\n')
  for line in lines:
    mo_offset = re.search(r'^(\d+): ', xxd_str)
    if mo_offset:
      line = line[mo_offset.end(0):]

    line = line.strip()
    while True:
      mo_data = re.search(r'^ ?([a-f0-9][a-f0-9][a-f0-9][a-f0-9])', line)
      if mo_data:
        word_str = mo_data.group(1)
        raw_bytes += struct.pack('B', int(word_str[0:2],16))
        raw_bytes += struct.pack('B', int(word_str[2:4],16))
        line = line[mo_data.end(0):]
      else:
        break

  return raw_bytes


class TestParseHexdump(unittest.TestCase):

  def test_single_line(self):
    test_data = '00000000: 5072 652d 4f72 6465 720a 0a53 575a 3031  Pre-Order..SWZ01'
    test_values = ParseHexdump(test_data)
    self.assertEquals(test_values, b'\x50\x72\x65\x2d\x4f\x72\x64\x65\x72\x0a\x0a\x53\x57\x5a\x30\x31')

  def test_multi_line(self):
    test_data = '00000000: 5072 652d 4f72 6465 720a 0a53 575a 3031  Pre-Order..SWZ01\n00000010: 202d 2058 2d57 696e 6720 5365 636f 6e64   - X-Wing Second\n00000020: 2045 6469 7469 6f6e 0a53 575a 3036 202d   Edition.SWZ06 -'
    test_values = ParseHexdump(test_data)
    self.assertEquals(test_values, b'\x50\x72\x65\x2d\x4f\x72\x64\x65\x72\x0a\x0a\x53\x57\x5a\x30\x31\x20\x2d\x20\x58\x2d\x57\x69\x6e\x67\x20\x53\x65\x63\x6f\x6e\x64\x20\x45\x64\x69\x74\x69\x6f\x6e\x0a\x53\x57\x5a\x30\x36\x20\x2d')

  def test_no_offset(self):
    test_data = '5072 652d 4f72 6465 720a 0a53 575a 3031  Pre-Order..SWZ01'
    test_values = ParseHexdump(test_data)
    self.assertEquals(test_values, b'\x50\x72\x65\x2d\x4f\x72\x64\x65\x72\x0a\x0a\x53\x57\x5a\x30\x31')

  def test_sub_line(self):
    test_data = '5072 652d 4f72 6465 720a'
    test_values = ParseHexdump(test_data)
    self.assertEquals(test_values, b'\x50\x72\x65\x2d\x4f\x72\x64\x65\x72\x0a')

  def test_ignore_ascii(self):
    test_data = '5072 652d 4f72 6465 720a  5072'
    test_values = ParseHexdump(test_data)
    self.assertEquals(test_values, b'\x50\x72\x65\x2d\x4f\x72\x64\x65\x72\x0a')


if __name__ == '__main__':
  if len(sys.argv) > 1:
      if sys.argv[1] == 'UNIT_TEST':
          del sys.argv[1]
          unittest.main()


