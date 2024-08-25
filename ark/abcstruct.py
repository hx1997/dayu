from common.binary_reader import BinaryReader


class AbcStructure:
    def __init__(self, bin_reader: BinaryReader, offset=None):
        self._bin_reader = bin_reader
        if offset:
            self._bin_reader.io.seek(offset)
