from pandasm.file import PandasmFile


class PandasmReader:
    def __init__(self):
        raise Exception(f'{self.__class__.__name__}: Use PandasmReader.from_file() or PandasmReader.from_buffer()')

    @classmethod
    def from_file(cls, filepath):
        with open(filepath, 'r', encoding='utf8', errors='ignore') as f:
            return cls.from_buffer(f.read())

    @classmethod
    def from_buffer(cls, buf):
        return cls.get_pandasm_file(buf)

    @classmethod
    def get_pandasm_file(cls, buf):
        return PandasmFile(buf)


if __name__ == '__main__':
    pandasm = PandasmReader.from_file(r"C:\Users\hx075\Desktop\pandasm\modules.abc.12.txt")
    print(pandasm.__dict__)
