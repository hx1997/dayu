from ark.abcstruct import AbcStructure
from common.binary_reader import BinaryReader


class ClassIndex(AbcStructure):
    def __init__(self, bin_reader: BinaryReader, num_classes, offset=None):
        super().__init__(bin_reader, offset)
        self.offsets = self._bin_reader.read_u32(num_classes)
