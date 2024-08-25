from ark.abcstruct import AbcStructure
from common.binary_reader import BinaryReader


class AbcHeader(AbcStructure):
    def __init__(self, bin_reader: BinaryReader, offset=None):
        super().__init__(bin_reader, offset)
        self.magic = None
        self.checksum = None
        self.version = None
        self.file_size = None
        self.foreign_off = None
        self.foreign_size = None
        self.num_classes = None
        self.class_idx_off = None
        self.num_lnps = None
        self.lnp_idx_off = None
        self.num_literalarrays = None  # deprecated
        self.literalarray_idx_off = None  # deprecated
        self.num_index_regions = None
        self.index_section_off = None

    @classmethod
    def check_magic(cls, magic):
        if magic != b'PANDA\0\0\0':
            raise ValueError(f'{cls.__name__}: not a valid abc file')

    @classmethod
    def get_version(cls, version):
        return version[0], version[1], version[2], version[3]
