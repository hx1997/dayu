from ark.abcstring import String
from ark.abcstruct import AbcStructure
from common.binary_reader import BinaryReader


class LocalExport(AbcStructure):
    def __init__(self, bin_reader: BinaryReader, offset=None):
        super().__init__(bin_reader, offset)
        self._local_name_offset = self._bin_reader.read_u32()
        self.local_name = String.read_string_with_pos_restore(self._bin_reader, self._local_name_offset).data
        self._export_name_offset = self._bin_reader.read_u32()
        self.export_name = String.read_string_with_pos_restore(self._bin_reader, self._export_name_offset).data
