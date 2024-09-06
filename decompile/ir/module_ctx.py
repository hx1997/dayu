import collections
import typing

from ark.abcfile.abcfile import AbcFile
from ark.abcliteralarray.module_literalarray import ModuleRecordLiteralArray


class IRModuleContext:
    def __init__(self, module):
        self.module = module
        # maps class names to the modules this class requests
        self.module_requests: typing.Dict[str, typing.List[dict]] = collections.defaultdict(list)

    def read_module_requests_from_abc(self, abcfile: AbcFile):
        for litarr in abcfile.literalarrays:
            if isinstance(litarr, ModuleRecordLiteralArray):
                class_name = litarr.declaring_class.name
                pandasm_class_name = self._abc_class_name_to_pandasm_class_name(class_name)
                for regular_import in litarr.regular_imports:
                    requested_module = litarr.module_requests[regular_import.module_request_idx]
                    self.module_requests[pandasm_class_name].append({
                        'regular_import': regular_import,
                        'requested_module': requested_module
                    })

    def _abc_class_name_to_pandasm_class_name(self, abc_class_name):
        if not abc_class_name.startswith('L') or not abc_class_name.endswith(';'):
            raise ValueError(f'{self.__class__.__name__}: not an abc class name')

        return abc_class_name[1:-1].replace('/', '.')

