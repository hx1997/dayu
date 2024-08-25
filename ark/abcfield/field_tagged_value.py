from ark.abcfield.field_tag import FieldTag
from ark.abcstring import String
from ark.tagged_value import TaggedValue


class FieldTaggedValue(TaggedValue):
    def read_tag(self) -> FieldTag:
        return FieldTag.from_bytes(self._bin_reader.read_bytes(1), byteorder='little')

    def read_data(self):
        self.tag: FieldTag
        if self.tag is FieldTag.NOTHING:
            return None
        elif self.tag is FieldTag.INT_VALUE:
            return self._bin_reader.read_sleb128()
        elif self.tag is FieldTag.VALUE:
            return self._bin_reader.read_u32()
        elif self.tag is FieldTag.RUNTIME_ANNOTATIONS:
            # TODO: implement
            print(f'Warning: FieldTag of type {self.tag.name} not implemented yet')
        elif self.tag is FieldTag.ANNOTATIONS:
            # TODO: implement
            print(f'Warning: FieldTag of type {self.tag.name} not implemented yet')
        elif self.tag is FieldTag.RUNTIME_TYPE_ANNOTATION:
            # TODO: implement
            print(f'Warning: FieldTag of type {self.tag.name} not implemented yet')
        elif self.tag is FieldTag.TYPE_ANNOTATION:
            # TODO: implement
            print(f'Warning: FieldTag of type {self.tag.name} not implemented yet')

