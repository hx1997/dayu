from ark.abcfield.field import Field
from ark.abcstring import String
from common.binary_reader import BinaryReader


class Field12(Field):
    def __init__(self, bin_reader: BinaryReader, offset=None):
        super().__init__(bin_reader, offset)
        self.class_idx = self._bin_reader.read_u16()
        self.type_idx = self._bin_reader.read_u16()
        self.name_off = self._bin_reader.read_u32()
        self.name = String.read_string_with_pos_restore(self._bin_reader, self.name_off).data
        self.reserved = self._bin_reader.read_uleb128()
        self.field_data = self.read_field_data()
