from ark.abcclass.abcclass import Class
from ark.abcfield.field9 import Field9
from ark.abcstring import String
from common.binary_reader import BinaryReader


class Class9(Class):
    def __init__(self, bin_reader: BinaryReader, offset=None):
        super().__init__(bin_reader, offset)
        self.name = String(bin_reader).data
        self.super_class_off = self._bin_reader.read_u32()
        self.access_flags = self._bin_reader.read_uleb128()
        self.num_fields = self._bin_reader.read_uleb128()
        self.num_methods = self._bin_reader.read_uleb128()
        self.class_data = self.read_class_data()
        self.fields = self.read_fields()
        self.methods = None

    def read_field(self):
        return Field9(self._bin_reader)
