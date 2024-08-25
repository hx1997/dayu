class PandasmInsn:
    def __init__(self, mnemonic, operands, label_name=''):
        self.mnemonic = mnemonic
        if operands != '':
            self.operands = self.read_operands(operands)
        else:
            self.operands = []
        self.label = label_name
        self.arguments = self.normalize_operands()

    def read_operands(self, operand_str):
        nest_level = 0
        inside_single_quote, inside_double_quote = False, False
        after_comma = False
        cur_operand = ''
        operands = []
        for ch in operand_str:
            if ch == ',' and nest_level == 0 and not inside_single_quote and not inside_double_quote:
                operands.append(cur_operand)
                cur_operand = ''
                after_comma = True
            elif ch in ['{', '[', '(']:
                nest_level += 1
                cur_operand += ch
            elif ch in ['}', ']', ')']:
                nest_level -= 1
                cur_operand += ch
            elif ch == "'":
                inside_single_quote = not inside_single_quote
                cur_operand += ch
            elif ch == '"':
                inside_double_quote = not inside_double_quote
                cur_operand += ch
            elif ch == ' ' and after_comma:
                after_comma = False
                continue
            else:
                cur_operand += ch
        if cur_operand:
            operands.append(cur_operand)
        return operands

    def normalize_operands(self):
        """
        normalize the operands by adding implicit operands (e.g., acc)
        normalized operands are called "arguments"
        """
        from decompile.ir.insn_enum import mnemonic2isainfo_map
        arg_types = mnemonic2isainfo_map[self.mnemonic]['arg_types'] if self.mnemonic in mnemonic2isainfo_map else None
        if arg_types:
            arguments = []
            operand_pos = 0
            for arg_type in arg_types:
                if arg_type == 'acc':
                    arguments.append(PandasmInsnArgument(arg_type))
                else:
                    arguments.append(PandasmInsnArgument(arg_type, self.operands[operand_pos]))
                    operand_pos += 1
            return arguments
        return None


class PandasmInsnArgument:
    def __init__(self, arg_type, arg_value=None, arg_ref_obj=None):
        """
        :param arg_type: can be one of:
          'acc', 'undefined', 'null', 'true', 'false', 'zero', 'FunctionObject', 'NewTarget',
          'cur_lexenv_level, 'lexenv_xxx', 'field', 'array', 'reg', 'str', 'imm', 'arr', 'module',
          'litarr', 'func', 'tmp', 'object'

        :param arg_value:
        :param arg_ref_obj:
        """
        self.type = arg_type
        self.value = arg_value

        # for some instructions like "definefieldbyname", one argument is interpreted with reference to another,
        # so we need to keep track of which object this argument references
        # for example, definefieldbyname 0x0, "stat", v4 means "dereference v4 to get the object,
        # then define a new field named 'stat' on it, and assign the contents of acc to the field"
        # in this case, self.value would be "stat", and self.ref_obj would be v4
        self.ref_obj = arg_ref_obj

    def __str__(self):
        if self.is_verbatim_type():
            return self.type if self.type != 'zero' else '0'
        elif self.type == 'field':
            if not self.ref_obj:
                raise RuntimeError(f'{self.__class__.__name__}: for arguments of "field" type, a reference object must be set')
            return f'{self.ref_obj}[{self.value}]'
        elif self.type == 'array':
            array_elems = [str(arg) for arg in self.value]
            return f'[{", ".join(array_elems)}]'
        elif self.type == 'object':
            obj_keys_values = [f'{k}: {v}' for k, v in self.value.items()]
            return '{' + ','.join(obj_keys_values) + '}'
        else:
            return f'{self.value}'

    def __eq__(self, other):
        if not isinstance(other, PandasmInsnArgument):
            return False
        return self.type == other.type and self.value == other.value and self.ref_obj == other.ref_obj

    def __hash__(self):
        if self.is_verbatim_type():
            return self.type.__hash__()
        elif self.type == 'array':
            elems_hash = sum([elem.__hash__() for elem in self.value])
            return self.type.__hash__() + elems_hash + (self.ref_obj.__hash__() if self.ref_obj else '<null>'.__hash__())
        elif self.type == 'object':
            elems_hash = sum([k.__hash__() + v.__hash__() for k, v in self.value.items()])
            return self.type.__hash__() + elems_hash + (self.ref_obj.__hash__() if self.ref_obj else '<null>'.__hash__())
        else:
            return self.type.__hash__() + (self.value.__hash__() if self.value else '<null>'.__hash__()) + (self.ref_obj.__hash__() if self.ref_obj else '<null>'.__hash__())

    def set_ref_obj(self, ref_obj):
        self.ref_obj = ref_obj

    def get_next_reg(self):
        """
        if this argument is of reg type, return a new reg-type PandasmInsnArgument representing the register
        that is next in number to that of this argument
        for example, if this argument represents reg:v0, calling this method will return a new PandasmInsnArgument
        representing reg:v1
        """
        assert self.type == 'reg'
        next_reg_num = int(self.value[1:]) + 1
        return PandasmInsnArgument('reg', f'v{next_reg_num}')

    def is_verbatim_type(self):
        return self.type in ['acc', 'undefined', 'null', 'true', 'false', 'zero', 'FunctionObject', 'NewTarget',
                         'cur_lexenv_level'] or self.type.startswith('lexenv')
