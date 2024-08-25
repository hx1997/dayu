from ark.abcstruct import AbcStructure
from common.binary_reader import BinaryReader


class TaggedValue(AbcStructure):
    def __init__(self, bin_reader: BinaryReader, offset=None):
        super().__init__(bin_reader, offset)
        self.tag = self.read_tag()
        self.data = self.read_data()

    def read_tag(self):
        raise NotImplementedError(f'{self.__class__.__name__}: Use one of the subclasses of TaggedValue instead of this abstract base')

    def read_data(self):
        raise NotImplementedError(f'{self.__class__.__name__}: Use one of the subclasses of TaggedValue instead of this abstract base')
