import struct
import leb128
from io import BytesIO


class BinaryReader:
    def __init__(self, io: BytesIO):
        if not isinstance(io, BytesIO):
            raise TypeError(f'{self.__class__.__name__}: input is not a BytesIO buffer')

        self.io = io

    def read_u8(self, count=1):
        if count == 1:
            return struct.unpack('B', self.io.read(1))[0]
        else:
            return struct.unpack(f'{count}B', self.io.read(1*count))

    def read_i8(self, count=1):
        if count == 1:
            return struct.unpack('b', self.io.read(1))[0]
        else:
            return struct.unpack(f'{count}b', self.io.read(1*count))

    def read_u16(self, count=1):
        if count == 1:
            return struct.unpack('H', self.io.read(2))[0]
        else:
            return struct.unpack(f'{count}H', self.io.read(2*count))

    def read_i16(self, count=1):
        if count == 1:
            return struct.unpack('h', self.io.read(2))[0]
        else:
            return struct.unpack(f'{count}h', self.io.read(2*count))

    def read_u32(self, count=1):
        if count == 1:
            return struct.unpack('I', self.io.read(4))[0]
        else:
            return struct.unpack(f'{count}I', self.io.read(4*count))

    def read_i32(self, count=1):
        if count == 1:
            return struct.unpack('i', self.io.read(4))[0]
        else:
            return struct.unpack(f'{count}i', self.io.read(4*count))

    def read_u64(self, count=1):
        if count == 1:
            return struct.unpack('Q', self.io.read(8))[0]
        else:
            return struct.unpack(f'{count}Q', self.io.read(8*count))

    def read_i64(self, count=1):
        if count == 1:
            return struct.unpack('q', self.io.read(8))[0]
        else:
            return struct.unpack(f'{count}q', self.io.read(8*count))

    def read_float32(self, count=1):
        if count == 1:
            return struct.unpack('f', self.io.read(4))[0]
        else:
            return struct.unpack(f'{count}f', self.io.read(4*count))

    def read_double64(self, count=1):
        if count == 1:
            return struct.unpack('d', self.io.read(8))[0]
        else:
            return struct.unpack(f'{count}d', self.io.read(8*count))

    def read_bytes(self, len):
        return struct.unpack(f'{len}s', self.io.read(len))[0]

    def read_uleb128(self):
        return leb128.u.decode_reader(self.io)[0]

    def read_sleb128(self):
        return leb128.i.decode_reader(self.io)[0]
