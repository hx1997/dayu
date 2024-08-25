import mutf8

from ark.abcstruct import AbcStructure
from common.binary_reader import BinaryReader


class String(AbcStructure):
    def __init__(self, bin_reader: BinaryReader, offset=None):
        super().__init__(bin_reader, offset)
        utf16_length = self._bin_reader.read_uleb128()
        self.len = utf16_length >> 1
        self.is_ascii = utf16_length & 1
        self.data = mutf8.decode_modified_utf8(self._bin_reader.read_bytes(self.len))
        self._bin_reader.read_u8()  # move the file pointer past the terminating null byte

    def __str__(self):
        return self.data

    @classmethod
    def read_string_with_pos_restore(cls, bin_reader: BinaryReader, offset=None):
        '''
        Read and return a String at the specified offset
        On return, the position of bin_reader will be restored to where it was when entering this method
        If offset is None, the reading will start at the current position of bin_reader
        '''
        pos = bin_reader.io.tell()
        string = cls(bin_reader, offset)
        bin_reader.io.seek(pos)
        return string
