from ark.abcstring import String
from ark.abcstruct import AbcStructure
from common.binary_reader import BinaryReader


class StarExport(AbcStructure):
    def __init__(self, bin_reader: BinaryReader, offset=None):
        super().__init__(bin_reader, offset)
        self.module_request_idx = self._bin_reader.read_u16()
