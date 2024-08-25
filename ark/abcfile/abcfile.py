import typing
from io import BytesIO

from ark.abcclass.abcclass import Class
from ark.abcclass.foreign_class import ForeignClass
from ark.abcfield.field_tag import FieldTag
from ark.abcclass.class_idx import ClassIndex
from ark.abcheader.header import AbcHeader
from ark.abcliteralarray.literalarray_idx import LiteralArrayIndex
from ark.abcliteralarray.module_literalarray import ModuleRecordLiteralArray
from common.binary_reader import BinaryReader
from input_file import DecompilerInputFile


class AbcFile(DecompilerInputFile):
    def __init__(self, buf):
        self._io = BytesIO(buf)
        self._bin_reader = BinaryReader(self._io)
        self.header: AbcHeader = self.read_header()
        self.version = self.header.get_version(self.header.version)
        self.class_idxs: ClassIndex = ClassIndex(self._bin_reader, self.header.num_classes, self.header.class_idx_off)
        self.classes: typing.Dict[str, typing.Union[Class, ForeignClass]] = self.read_classes()
        # this is a dict that maps a module record to its declaring class,
        # so that we know which class this module record belongs to
        self._modulerecord_literalarr_offs = self.read_modulerecord_literalarr_offs()
        self.literalarray_idxs: LiteralArrayIndex = LiteralArrayIndex(self._bin_reader, self.header.num_literalarrays,
                                                                      self.header.literalarray_idx_off)
        self.literalarrays = self.read_literalarrays()

    def read_header(self):
        raise Exception("Do not use this class directly. Use AbcReader.from_{file,buffer}() to create an instance.")

    def read_classes(self):
        raise Exception("Do not use this class directly. Use AbcReader.from_{file,buffer}() to create an instance.")

    def read_literalarrays(self):
        literalarrays = []
        for offset in self.literalarray_idxs.offsets:
            if offset in self._modulerecord_literalarr_offs:
                literalarray = ModuleRecordLiteralArray(self._bin_reader,
                                                              self._modulerecord_literalarr_offs[offset], offset)
                literalarrays.append(literalarray)
                # add a reference of this module record to the declaring class
                # to make it easier to know which modules are imported/exported for a specific class
                self._modulerecord_literalarr_offs[offset].module_record = literalarray
        return literalarrays

    def read_modulerecord_literalarr_offs(self):
        modulerecord_literalarrs = {}
        for clz in self.iter_local_classes():
            field = clz.get_field_by_name('moduleRecordIdx')
            if field:
                for field_data in field.field_data:
                    if field_data.tag is FieldTag.VALUE:
                        modulerecord_literalarrs[field_data.data] = clz
        return modulerecord_literalarrs

    def is_foreign_region(self, offset):
        return self.header.foreign_off <= offset < self.header.foreign_off + self.header.foreign_size

    def iter_local_classes(self):
        for clz_name, clz in self.classes.items():
            if isinstance(clz, Class):
                yield clz

    def iter_foreign_classes(self):
        for clz_name, clz in self.classes.items():
            if isinstance(clz, ForeignClass):
                yield clz

    @classmethod
    def from_file(cls, filepath):
        with open(filepath, 'rb') as f:
            return cls.from_buffer(f.read())

    @classmethod
    def from_buffer(cls, buf):
        return cls(buf)


if __name__ == '__main__':
    AbcFile.from_file(r"C:\Users\hx075\Desktop\pandasm\modules.abc")
