import typing

from ark.abcfield.field_tag import FieldTag
from ark.abcfield.field_tagged_value import FieldTaggedValue
from ark.abcstruct import AbcStructure
from common.binary_reader import BinaryReader


class Field(AbcStructure):
    def __init__(self, bin_reader: BinaryReader, offset=None):
        super().__init__(bin_reader, offset)
        self.class_idx = None
        self.type_idx = None
        self.name_off = None
        self.name = None
        self.field_data: typing.List[FieldTaggedValue] = None

    def read_field_data(self):
        self.field_data = []
        field_data_item = FieldTaggedValue(self._bin_reader)
        self.field_data.append(field_data_item)
        while field_data_item.tag is not FieldTag.NOTHING:
            field_data_item = FieldTaggedValue(self._bin_reader)
            self.field_data.append(field_data_item)
        return self.field_data