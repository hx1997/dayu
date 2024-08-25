from ark.abcheader.header import AbcHeader
from common.binary_reader import BinaryReader


class AbcHeader12(AbcHeader):
    def __init__(self, bin_reader: BinaryReader):
        super().__init__(bin_reader)
        self.magic = self._bin_reader.read_bytes(8)
        self.check_magic(self.magic)
        self.checksum = self._bin_reader.read_u32()
        self.version = self._bin_reader.read_bytes(4)
        self.check_version()
        self.file_size = self._bin_reader.read_u32()
        self.foreign_off = self._bin_reader.read_u32()
        self.foreign_size = self._bin_reader.read_u32()
        self.num_classes = self._bin_reader.read_u32()
        self.class_idx_off = self._bin_reader.read_u32()
        self.num_lnps = self._bin_reader.read_u32()
        self.lnp_idx_off = self._bin_reader.read_u32()
        self.num_literalarrays = self._bin_reader.read_u32()  # deprecated
        self.literalarray_idx_off = self._bin_reader.read_u32()  # deprecated
        self.num_index_regions = self._bin_reader.read_u32()
        self.index_section_off = self._bin_reader.read_u32()

    def check_version(self):
        major, minor, feature, build = self.get_version(self.version)
        if major < 12 or feature < 1:
            raise ValueError(f'{self.__class__.__name__}: abc version mismatch, expected >= 12.0.1.0, got {major}.{minor}.{feature}.{build}. Use the correct version of AbcHeader!')

