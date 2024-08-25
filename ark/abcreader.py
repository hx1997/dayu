from io import BytesIO

from ark.abcfile.abcfile import AbcFile
from ark.abcfile.abcfile9 import AbcFile9
from ark.abcfile.abcfile12 import AbcFile12
from ark.abcheader.header import AbcHeader
from common.binary_reader import BinaryReader


class AbcReader:
    def __init__(self):
        raise Exception(f'{self.__class__.__name__}: Use AbcReader.from_file() or AbcReader.from_buffer()')

    @classmethod
    def from_file(cls, filepath):
        with open(filepath, 'rb') as f:
            return cls.from_buffer(f.read())

    @classmethod
    def from_buffer(cls, buffer):
        io = BytesIO(buffer)
        reader = BinaryReader(io)

        magic = reader.read_bytes(8)
        AbcHeader.check_magic(magic)
        checksum = reader.read_u32()
        version = reader.read_bytes(4)
        return cls.get_abc_file(buffer, version)

    @classmethod
    def get_abc_file(cls, buf, version):
        major, minor, feature, build = version
        if major >= 12 and minor >= 0 and feature >= 1 and build >= 0:
            return AbcFile12.from_buffer(buf)
        elif major >= 9 and minor >= 0 and feature >= 0 and build >= 0:
            return AbcFile9.from_buffer(buf)
        else:
            raise NotImplementedError(f'{cls.__name__}: unsupported abc version {major}.{minor}.{feature}.{build}')

if __name__ == '__main__':
    abc: AbcFile = AbcReader.from_file(r"C:\Users\hx075\Desktop\pandasm\modules12.abc")
    print(abc.__dict__)
    abc: AbcFile = AbcReader.from_file(r"C:\Users\hx075\Desktop\pandasm\modules.abc")
    print(abc.__dict__)
