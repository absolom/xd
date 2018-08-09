"""Inteded to be used with vim's selected text filter command to convert xxd output
to parsed structures/bitfields."""

import re
import struct
import unittest
import sys
import argparse
import math
import ctypes

def RenderFields(field_tuples):
  ret = '\n'
  for name, value in field_tuples:
    ret += '{:s}  :  0x{:x} ({:d})\n'.format(name, value, value)

  return ret

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

  byte_values = []
  for i in range(0, len(raw_bytes)):
    byte_values.append(struct.unpack('B', raw_bytes[i])[0])

  return byte_values


class FieldBase:
  def __init__(self, width):
    self.values = []
    self.width = width

    if self.getTotalBits() % 8 != 0:
      raise ValueError('Illegal field size.')

  def getValues(self):
    return self.values

  def getWidth(self):
    return self.width

  def getTotalBytes(self):
    return int(self.getTotalBits() / 8)
    
  def applyEndianness(self, endianness):
    if endianness == 'little':
      self.width.reverse()



class Field(FieldBase):

  def getTotalBits(self):
    return self.width

  def consumeBytes(self, field_bytes, endianness='little'):
    field_bytes.reverse()
    value = 0
    for i,b in enumerate(field_bytes):
      value += b << 8 * i
      
    self.values.append(value)



class Bitfield(FieldBase):

  def getTotalBits(self):
    return sum(self.width)

  def consumeBytes(self, field_bytes, endianness='little'):
    self.values = []
    self.applyEndianness(endianness)
      
    cur_byte = None
    cur_byte_valid_bits = 0
    bitfield_values = []
    for width in self.getWidth():
      value = 0

      while width > 0:

        if cur_byte_valid_bits == 0:
          cur_byte_valid_bits = 8
          cur_byte = field_bytes.pop(0)

        if width < cur_byte_valid_bits:
          bitshift = cur_byte_valid_bits - width
          bitmask = int(math.pow(2, width)) - 1
          consumed_bits = width
        else:
          bitshift = 0
          bitmask = int(math.pow(2, cur_byte_valid_bits)) - 1
          consumed_bits = cur_byte_valid_bits

        width -= consumed_bits
        value += (bitmask & (cur_byte >> bitshift)) << width
        cur_byte_valid_bits -= consumed_bits

      bitfield_values.append(value)

    if endianness == 'little':
      bitfield_values.reverse()
    
    self.values += bitfield_values



class Structure:

  def __init__(self, def_str):
    tokens = def_str.split('|') 
    fields = []
    is_bitfield = []
    total_bits = 0
    for token in tokens:
        if ':' in token:
          bitfield = []
          values = token.split(':')
          for value in values:
            v = int(value)
            total_bits += v
            bitfield.append(v)
          fields.append(bitfield)
          is_bitfield.append(True)
        else:
          v = int(token)
          total_bits += v
          fields.append(v)
          is_bitfield.append(False)

    self.fields = fields
    self.is_bitfield = is_bitfield
    self.total_bits = total_bits

  def apply(self, byte_data, word_size=4, endianness='little'):
    if self.total_bits > 8 * len(byte_data):
      raise ValueError('Not enough xxd data.')
  
    values = []
    for field in self:
  
      field_total_bytes = field.getTotalBytes()
      field_bytes = byte_data[0:field_total_bytes]
      del byte_data[0:field_total_bytes]
  
      if endianness == 'little':
        field_bytes.reverse()

      field.consumeBytes(field_bytes, endianness=endianness)
      values += field.getValues()
  
    return values

  def __iter__(self):
    for i,_ in enumerate(self.fields):
      if self.is_bitfield[i]:
        yield Bitfield(self.fields[i])
      else:
        yield Field(self.fields[i])
      #yield Structure.Field(self.is_bitfield[i], self.fields[i])
 
  def getTotalBits(self):
    return self.total_bits



class TestStructure_Apply(unittest.TestCase):

  def test_basic(self):
    values = Structure('5:7:12:8|8|24').apply([0x59,0x5c,0xa4,0x32,0x18,0x56,0x34,0x12])
    self.assertEquals(values, [0x19,0x62,0xa45,0x32,0x18,0x123456])

  def test_single_field(self):
    values = Structure('8').apply([0x59])
    self.assertEquals(values, [0x59])

  def test_single_bitfield(self):
    values = Structure('4:4').apply([0x59])
    self.assertEquals(values, [0x9, 0x5])
    
    values = Structure('4:4').apply([0x59], endianness='big')
    self.assertEquals(values, [0x5, 0x9])

  def test_bad_bitfield_size(self):
    s = Structure('5:7:2:9|8|24')
    self.assertRaises(ValueError, s.apply, [0x59,0x5c,0xa4,0x32,0x18,0x56,0x34,0x12,0x0], endianness='big')

  def test_not_enough_data(self):
    s = Structure('5:7:2:8|8|24')
    self.assertRaises(ValueError, s.apply, [0x59])



class TestStructure(unittest.TestCase):

  def test_bad_char(self):
    self.assertRaises(ValueError, Structure, '5:7:2a:8|8|24')



class TestParseHexdump(unittest.TestCase):

  def test_single_line(self):
    test_data = '00000000: 5072 652d 4f72 6465 720a 0a53 575a 3031  Pre-Order..SWZ01'
    test_values = ParseHexdump(test_data)
    self.assertEquals(test_values, [0x50, 0x72, 0x65, 0x2d, 0x4f, 0x72, 0x64, 0x65, 0x72, 0x0a, 0x0a, 0x53, 0x57, 0x5a, 0x30, 0x31])

  def test_multi_line(self):
    test_data = '00000000: 5072 652d 4f72 6465 720a 0a53 575a 3031  Pre-Order..SWZ01\n00000010: 202d 2058 2d57 696e 6720 5365 636f 6e64   - X-Wing Second\n00000020: 2045 6469 7469 6f6e 0a53 575a 3036 202d   Edition.SWZ06 -'
    test_values = ParseHexdump(test_data)
    self.assertEquals(test_values, [0x50, 0x72, 0x65, 0x2d, 0x4f, 0x72, 0x64, 0x65, 0x72, 0x0a, 0x0a, 0x53, 0x57, 0x5a, 0x30, 0x31, 0x20, 0x2d, 0x20, 0x58, 0x2d, 0x57, 0x69, 0x6e, 0x67, 0x20, 0x53, 0x65, 0x63, 0x6f, 0x6e, 0x64, 0x20, 0x45, 0x64, 0x69, 0x74, 0x69, 0x6f, 0x6e, 0x0a, 0x53, 0x57, 0x5a, 0x30, 0x36, 0x20, 0x2d])

  def test_no_offset(self):
    test_data = '5072 652d 4f72 6465 720a 0a53 575a 3031  Pre-Order..SWZ01'
    test_values = ParseHexdump(test_data)
    self.assertEquals(test_values, [0x50, 0x72, 0x65, 0x2d, 0x4f, 0x72, 0x64, 0x65, 0x72, 0x0a, 0x0a, 0x53, 0x57, 0x5a, 0x30, 0x31])

  def test_sub_line(self):
    test_data = '5072 652d 4f72 6465 720a'
    test_values = ParseHexdump(test_data)
    self.assertEquals(test_values, [0x50, 0x72, 0x65, 0x2d, 0x4f, 0x72, 0x64, 0x65, 0x72, 0x0a])

  def test_ignore_ascii(self):
    test_data = '5072 652d 4f72 6465 720a  5072'
    test_values = ParseHexdump(test_data)
    self.assertEquals(test_values, [0x50, 0x72, 0x65, 0x2d, 0x4f, 0x72, 0x64, 0x65, 0x72, 0x0a])



class TestCommandLine(unittest.TestCase):

  def setUp(self):
    field_tuples = []
    field_tuples.append(('field0', 0x50))
    field_tuples.append(('field1', 0x72))
    field_tuples.append(('field2', 0x65))
    field_tuples.append(('field3', 0x2d))
    field_tuples.append(('field4', 0x6564724f))
    field_tuples.append(('field5', 0x530a0a72))

    self.truth = RenderFields(field_tuples)

  def test_sanity_arg(self):
    import subprocess
    output = subprocess.check_output('python xxd-parse.py "8:8:8:8|32|32" "00000000: 5072 652d 4f72 6465 720a 0a53 575a 3031  Pre-Order..SWZ01\n00000010: 202d 2058 2d57 696e 6720 5365 636f 6e64   - X-Wing Second\n00000020: 2045 6469 7469 6f6e 0a53 575a 3036 202d   Edition.SWZ06 -" --field_names="field0 field1 field2 field3 field4 field5"', shell=True)
    self.assertEquals(output, self.truth)

  def test_sanity_stdin(self):
    import subprocess
    output = subprocess.check_output('echo "00000000: 5072 652d 4f72 6465 720a 0a53 575a 3031  Pre-Order..SWZ01\n00000010: 202d 2058 2d57 696e 6720 5365 636f 6e64   - X-Wing Second\n00000020: 2045 6469 7469 6f6e 0a53 575a 3036 202d   Edition.SWZ06 -" | python xxd-parse.py "8:8:8:8|32|32" - --field_names="field0 field1 field2 field3 field4 field5"', shell=True)
    self.assertEquals(output, self.truth)

  def test_sanity_stdin_implicit(self):
    import subprocess
    output = subprocess.check_output('echo "00000000: 5072 652d 4f72 6465 720a 0a53 575a 3031  Pre-Order..SWZ01\n00000010: 202d 2058 2d57 696e 6720 5365 636f 6e64   - X-Wing Second\n00000020: 2045 6469 7469 6f6e 0a53 575a 3036 202d   Edition.SWZ06 -" | python xxd-parse.py "8:8:8:8|32|32" --field_names="field0 field1 field2 field3 field4 field5"', shell=True)
    self.assertEquals(output, self.truth)



if __name__ == '__main__':

  if len(sys.argv) > 1:
    if sys.argv[1] == 'UNIT_TEST':
      del sys.argv[1]
      unittest.main()
  
  parser = argparse.ArgumentParser(description='Converts xxd output to parsed structs/bitfields.')
  parser.add_argument('bitfield', help='bit widths of each field')
  parser.add_argument('xxd_output', nargs='?', default='-', help='xxd output to parse')
  parser.add_argument('--field_names', default='', help='name of each field')
  parser.add_argument('--endianness', default='little', help='endianness of the data, big or little*')
  parser.add_argument('--word_size_bits', type=int, default=4, help='Word size in bits, default is 32')
  args = parser.parse_args()

  ####

  # TODO : Make '-' the default
  # TODO : Add config file which supports shortcuts for common struct defs and fieldnames

  if args.xxd_output == '-':
    args.xxd_output = sys.stdin.read()

  byte_data = ParseHexdump(args.xxd_output)
  s = Structure(args.bitfield)
  field_values = s.apply(byte_data, word_size=args.word_size_bits, endianness=args.endianness)

  field_tuples = []
  for i,field in enumerate(args.field_names.split(' ')):
    field_tuples.append((field, field_values[i]))

  out = RenderFields(field_tuples)
  sys.stdout.write(out)

