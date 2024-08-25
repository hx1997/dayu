from ark.abcclass.class_tag import ClassTag
from ark.abcstring import String
from ark.tagged_value import TaggedValue


class ClassTaggedValue(TaggedValue):
    def read_tag(self) -> ClassTag:
        return ClassTag.from_bytes(self._bin_reader.read_bytes(1), byteorder='little')

    def read_data(self):
        self.tag: ClassTag
        if self.tag is ClassTag.NOTHING:
            return None
        elif self.tag is ClassTag.INTERFACES:
            num_interfaces = self._bin_reader.read_uleb128()
            interfaces_idx = self._bin_reader.read_u16(num_interfaces)
            return {'num_interfaces': num_interfaces, 'interfaces_idx': interfaces_idx}
        elif self.tag is ClassTag.SOURCE_LANG:
            return self._bin_reader.read_u8()
        elif self.tag is ClassTag.RUNTIME_ANNOTATION:
            # TODO: implement
            print(f'Warning: ClassTag of type {self.tag.name} not implemented yet')
        elif self.tag is ClassTag.ANNOTATION:
            # TODO: implement
            print(f'Warning: ClassTag of type {self.tag.name} not implemented yet')
        elif self.tag is ClassTag.RUNTIME_TYPE_ANNOTATION:
            # TODO: implement
            print(f'Warning: ClassTag of type {self.tag.name} not implemented yet')
        elif self.tag is ClassTag.TYPE_ANNOTATION:
            # TODO: implement
            print(f'Warning: ClassTag of type {self.tag.name} not implemented yet')
        elif self.tag is ClassTag.SOURCE_FILE:
            pos = self._bin_reader.io.tell()
            source_file = String.read_string_with_pos_restore(self._bin_reader, self._bin_reader.read_u32()).data
            self._bin_reader.io.seek(pos)
            return source_file

