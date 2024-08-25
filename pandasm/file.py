from input_file import DecompilerInputFile
from io import StringIO
from enum import IntEnum, auto

from common.simple_lexer import SimpleLexer
from pandasm.field import PandasmField
from pandasm.insn import PandasmInsn
from pandasm.method import PandasmMethod
from pandasm.pa_class import PandasmClass


class PAReaderState(IntEnum):
    INITIAL = auto()
    PRE_DIRECTIVE = auto()
    BAR = auto()
    SOURCE_BINARY = auto()
    PRE_LITERALS = auto()
    LITERALS = auto()
    PRE_RECORDS = auto()
    RECORDS = auto()
    PRE_METHODS = auto()
    SLOT_NUMBER_ANNOTATION = auto()
    METHODS = auto()
    PRE_STRING = auto()
    STRING = auto()
    LANGUAGE = auto()
    ERROR = auto()
    END = auto()


class PandasmFile(DecompilerInputFile):
    def __init__(self, buf):
        self._io = StringIO(buf)
        self._lexer = SimpleLexer(self._io)

        # Pandasm sections
        self.source_binary = ''
        self.language = ''
        self.classes = {}

        self.read()

    # Finite State Machine:
    #   INITIAL state - no token eaten yet
    #   PRE_DIRECTIVE state - just ate a # at the beginning of line
    #   BAR state - just ate the === bar separating different sections
    #   SOURCE_BINARY state
    #   PRE_LITERALS state
    #   LITERALS state
    #   PRE_RECORDS state
    #   RECORDS state
    #   PRE_METHODS state
    #   SLOT_NUMBER_ANNOTATION state - processing L_ESSlotNumberAnnotation that appears before each method (API 11+)
    #   METHODS state
    #   PRE_STRING state
    #   STRING state
    #   LANGUAGE state - processing pseudo-instruction .language
    #   ERROR state
    #
    def read(self):
        state = PAReaderState.INITIAL
        while state is not PAReaderState.END:
            try:
                # Dispatch to the handlers for each state
                if state is PAReaderState.INITIAL:
                    state = self.__process_initial()
                elif state is PAReaderState.PRE_DIRECTIVE:
                    state = self.__process_pre_directive()
                elif state is PAReaderState.SOURCE_BINARY:
                    state = self.__process_source_binary()
                elif state is PAReaderState.LANGUAGE:
                    state = self.__process_language()
                elif state is PAReaderState.BAR:
                    state = self.__try_determine_state_by_next_token(self._lexer.next_token())
                elif state is PAReaderState.PRE_LITERALS:
                    state = self.__process_pre_literals()
                elif state is PAReaderState.PRE_RECORDS:
                    state = self.__process_pre_records()
                elif state is PAReaderState.PRE_METHODS:
                    state = self.__process_pre_methods()
                elif state is PAReaderState.RECORDS:
                    state = self.__process_records()
                elif state is PAReaderState.SLOT_NUMBER_ANNOTATION:
                    state = self.__process_slot_number_annotation()
                elif state is PAReaderState.METHODS:
                    state = self.__process_methods()
                elif state is PAReaderState.PRE_STRING:
                    state = self.__process_pre_string()
                elif state is PAReaderState.ERROR:
                    print(f'{self.__class__.__name__}: error encountered when reading pandasm file')
                    break
                else:
                    print(f'{self.__class__.__name__}: unexpected state {state.name}')
                    break
            except StopIteration:
                # StopIteration means EOF was encountered when trying to read next token
                state = PAReaderState.END

        return state.name

    def __try_determine_state_by_next_token(self, next_token):
        '''
        Try to determine the next state by the next token
        This is often useful when we're at the beginning of a line starting with
        some giveaway strings like ".record", which means we have class records
        coming up next
        '''
        if next_token == '#':
            return PAReaderState.PRE_DIRECTIVE
        elif next_token == '.language':
            return PAReaderState.LANGUAGE
        elif next_token == '.record':
            return PAReaderState.RECORDS
        elif next_token == '.function':
            return PAReaderState.METHODS
        elif next_token == 'L_ESSlotNumberAnnotation:\n':
            return PAReaderState.SLOT_NUMBER_ANNOTATION
        else:
            return PAReaderState.ERROR

    def __process_initial(self):
        next_token = self._lexer.next_token()
        return self.__try_determine_state_by_next_token(next_token)

    def __process_pre_directive(self):
        next_token = self._lexer.next_token()
        if next_token == 'source':
            state = PAReaderState.SOURCE_BINARY
        elif next_token == '====================\n':
            state = PAReaderState.BAR
        elif next_token == 'LITERALS\n':
            state = PAReaderState.PRE_LITERALS
        elif next_token == 'RECORDS\n':
            state = PAReaderState.PRE_RECORDS
        elif next_token == 'METHODS\n':
            state = PAReaderState.PRE_METHODS
        elif next_token == 'STRING\n':
            state = PAReaderState.PRE_STRING
        else:
            state = PAReaderState.ERROR
        return state

    def __process_source_binary(self):
        self._lexer.next_token()
        self.source_binary = self._lexer.read_until_next_line()
        next_token = self._lexer.next_token()
        return self.__try_determine_state_by_next_token(next_token)

    def __process_language(self):
        self.language = self._lexer.read_until_next_line()
        next_token = self._lexer.next_token()
        return self.__try_determine_state_by_next_token(next_token)

    def __process_pre_literals(self):
        # TODO: 处理 literals，目前只是跳过这部分
        self._lexer.read_until_token('#')
        return PAReaderState.PRE_DIRECTIVE

    def __process_pre_records(self):
        # TODO: 处理 records，目前只是跳过这部分
        # self._lexer.read_until_token('#')
        # return PAReaderState.PRE_DIRECTIVE
        next_token = self._lexer.next_token()
        return self.__try_determine_state_by_next_token(next_token)

    def __process_records(self):
        class_name = self._lexer.next_token()
        clz = PandasmClass(class_name)
        self.classes[class_name] = clz
        next_token = self._lexer.next_token()
        if next_token == '{\n':
            # record body starts
            body_line = self._lexer.read_until_next_line()
            while body_line != '}':
                field_type, field_name, _, field_value = body_line.split()
                clz.fields.append(PandasmField(field_name, field_type, field_value))
                body_line = self._lexer.read_until_next_line()
            # record body ends
        return PAReaderState.PRE_RECORDS

    def __process_pre_methods(self):
        next_token = self._lexer.next_token()
        return self.__try_determine_state_by_next_token(next_token)

    def __process_methods(self):
        return_type = self._lexer.next_token()
        method_name_args_flags = self._lexer.read_until_token('{\n')
        # print(f'{return_type} {method_name_args_flags}')

        # extract method name, arguments, and flags
        class_method_name, args_flags = method_name_args_flags.strip('{\n').split('(')
        class_method_name_split = class_method_name.split('.')
        class_name, method_name = '.'.join(class_method_name_split[:-1]), class_method_name_split[-1]
        args_flags_split = args_flags.split(')')
        method_args, flags = args_flags_split[0], args_flags_split[1].strip()

        # print(method_name, method_args)
        method = PandasmMethod(method_name, return_type, method_args)
        self.classes[class_name].methods.append(method)

        # method body starts
        body_line = self._lexer.read_until_next_line()
        last_label_name = ''
        while body_line != '}':
            # extract instruction opcodes and operands
            if body_line.endswith(':'):
                # this is a label, not an instruction
                last_label_name = body_line[:-1]
            elif body_line.startswith('.'):
                # this is a pseudo-instruction
                # TODO: implement
                pass
            else:
                # now we have an instruction
                line_split = body_line.split()
                opcode, operands = line_split[0], ' '.join(line_split[1:])
                method.insns.append(PandasmInsn(opcode, operands, last_label_name))
                last_label_name = ''
            body_line = self._lexer.read_until_next_line()
        # method body ends
        return PAReaderState.PRE_METHODS

    def __process_pre_string(self):
        # TODO: 处理 string，目前只是跳过这部分，而且假设 string 永远位于 Panda Assembly 的最后一部分
        line = self._lexer.read_until_next_line()
        while True:
            line = self._lexer.read_until_next_line()
        return PAReaderState.PRE_DIRECTIVE

    def __process_slot_number_annotation(self):
        self._lexer.read_until_token('.function')
        return PAReaderState.METHODS
