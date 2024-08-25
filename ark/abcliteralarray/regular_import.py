from ark.abcstring import String
from ark.abcstruct import AbcStructure
from common.binary_reader import BinaryReader


class RegularImport(AbcStructure):
    def __init__(self, bin_reader: BinaryReader, offset=None):
        super().__init__(bin_reader, offset)
        self._local_name_offset = self._bin_reader.read_u32()
        self.local_name = String.read_string_with_pos_restore(self._bin_reader, self._local_name_offset).data
        self._import_name_offset = self._bin_reader.read_u32()
        self.import_name = String.read_string_with_pos_restore(self._bin_reader, self._import_name_offset).data
        self.module_request_idx = self._bin_reader.read_u16()
