from ark.abcclass.abcclass import Class
from ark.abcliteralarray.indirect_export import IndirectExport
from ark.abcliteralarray.local_export import LocalExport
from ark.abcliteralarray.namespace_import import NamespaceImport
from ark.abcliteralarray.regular_import import RegularImport
from ark.abcliteralarray.star_export import StarExport
from ark.abcstring import String
from ark.abcstruct import AbcStructure
from common.binary_reader import BinaryReader


class ModuleRecordLiteralArray(AbcStructure):
    def __init__(self, bin_reader: BinaryReader, declaring_class, offset=None):
        super().__init__(bin_reader, offset)
        self.declaring_class: Class = declaring_class

        self.num_literals = self._bin_reader.read_u32()

        self.num_module_requests = self._bin_reader.read_u32()
        self._module_requests_offs = []
        self.module_requests = []
        for _ in range(self.num_module_requests):
            module_request_off = self._bin_reader.read_u32()
            self._module_requests_offs.append(module_request_off)
            module_request = String.read_string_with_pos_restore(self._bin_reader, module_request_off).data
            self.module_requests.append(module_request)

        self.regular_import_num = self._bin_reader.read_u32()
        self._regular_imports_offs = []
        self.regular_imports = []
        for _ in range(self.regular_import_num):
            regular_import = RegularImport(self._bin_reader)
            self.regular_imports.append(regular_import)

        self.namespace_import_num = self._bin_reader.read_u32()
        self._namespace_imports_offs = []
        self.namespace_imports = []
        for _ in range(self.namespace_import_num):
            namespace_import = NamespaceImport(self._bin_reader)
            self.namespace_imports.append(namespace_import)

        self.local_export_num = self._bin_reader.read_u32()
        self._local_exports_offs = []
        self.local_exports = []
        for _ in range(self.local_export_num):
            local_export = LocalExport(self._bin_reader)
            self.local_exports.append(local_export)

        self.indirect_export_num = self._bin_reader.read_u32()
        self._indirect_exports_offs = []
        self.indirect_exports = []
        for _ in range(self.indirect_export_num):
            indirect_export = IndirectExport(self._bin_reader)
            self.indirect_exports.append(indirect_export)

        self.star_export_num = self._bin_reader.read_u32()
        self._star_exports_offs = []
        self.star_exports = []
        for _ in range(self.star_export_num):
            star_export = StarExport(self._bin_reader)
            self.star_exports.append(star_export)
