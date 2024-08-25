from ark.abcclass.abcclass9 import Class9
from ark.abcclass.foreign_class import ForeignClass
from ark.abcfile.abcfile import AbcFile
from ark.abcheader.header9 import AbcHeader9


class AbcFile9(AbcFile):
    def read_header(self):
        return AbcHeader9(self._bin_reader)

    def read_classes(self):
        classes = {}
        for offset in self.class_idxs.offsets:
            if self.is_foreign_region(offset):
                clz = ForeignClass(self._bin_reader, offset)
                classes[clz.name] = clz
            else:
                clz = Class9(self._bin_reader, offset)
                classes[clz.name] = clz
        return classes


if __name__ == '__main__':
    AbcFile9.from_file(r"C:\Users\hx075\Desktop\pandasm\modules.abc")
