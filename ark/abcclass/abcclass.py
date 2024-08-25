import typing

from ark.abcclass.class_tag import ClassTag
from ark.abcclass.class_tagged_value import ClassTaggedValue
from ark.abcfield.field import Field
from ark.abcstruct import AbcStructure
from common.binary_reader import BinaryReader


class Class(AbcStructure):
    def __init__(self, bin_reader: BinaryReader, offset=None):
        super().__init__(bin_reader, offset)
        self.name = None
        self.access_flags = None
        self.num_fields = None
        self.num_methods = None
        self.class_data: typing.List[ClassTaggedValue] = []
        self.fields: typing.List[Field] = []
        self.methods = None  # TODO: implement
        self.module_record = None  # this will be filled out when parsing LiteralArrays

    def read_class_data(self):
        self.class_data = []
        class_data_item = ClassTaggedValue(self._bin_reader)
        self.class_data.append(class_data_item)
        while class_data_item.tag is not ClassTag.NOTHING:
            class_data_item = ClassTaggedValue(self._bin_reader)
            self.class_data.append(class_data_item)
        return self.class_data

    def read_field(self):
        raise NotImplementedError(f'{self.__class__.__name__}: Use one of the subclasses of Class instead of this abstract base')

    def read_method(self):
        raise NotImplementedError(f'{self.__class__.__name__}: Use one of the subclasses of Class instead of this abstract base')

    def read_fields(self):
        fields = []
        for _ in range(self.num_fields):
            fields.append(self.read_field())
        return fields

    def read_methods(self):
        methods = []
        for _ in range(self.num_methods):
            methods.append(self.read_method())
        return methods

    def get_field_by_name(self, name):
        for field in self.fields:
            if field.name == name:
                return field

    def get_method_by_name(self, name):
        for method in self.methods:
            if method.name == name:
                return method
