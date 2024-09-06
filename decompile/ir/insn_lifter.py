from decompile.ir.builder import IRBuilder
from decompile.ir.nac import NAddressCode
from pandasm.insn import PandasmInsn, PandasmInsnArgument


class InsnLifter:
    """
    All the lifters for raw bytecode instructions
    This class should only contain lifters and nothing else (methods, fields, etc)
    because the mnemonic to lifter map is generated automatically from InsnLifter.__dict__
    """
    @staticmethod
    def ldundefined(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(PandasmInsnArgument('undefined'), label=insn.label)

    @staticmethod
    def ldnull(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(PandasmInsnArgument('null'), label=insn.label)

    @staticmethod
    def ldtrue(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(PandasmInsnArgument('true'), label=insn.label)

    @staticmethod
    def ldfalse(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(PandasmInsnArgument('false'), label=insn.label)

    @staticmethod
    def createemptyobject(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(PandasmInsnArgument('object', {}), label=insn.label)

    @staticmethod
    def createobjectwithbuffer(insn: NAddressCode, builder: IRBuilder):
        obj = insn.args[2].value  # createobjectwithbuffer 0x37, { 4 [ string:"height", null_value:0, string:"width", null_value:0, ]}
        obj = obj.split('[')[1].split(']')[0].strip()  # string:"height", null_value:0, string:"width", null_value:0,
        # `obj` is an array of alternating keys and values, keep a variable so we know we're dealing with a key or a value as we go
        key_or_value = 'key'
        is_inside_quotes, is_after_comma = False, False
        cur_str = ''
        keys, values = [], []
        for ch in obj:
            if ch == '"':
                is_inside_quotes = not is_inside_quotes
            elif ch == ',':
                if not is_inside_quotes:
                    if key_or_value == 'key':
                        key_or_value = 'value'
                        keys.append(cur_str)
                    elif key_or_value == 'value':
                        key_or_value = 'key'
                        values.append(cur_str)
                    cur_str = ''
                    is_after_comma = True
                else:
                    cur_str += ch
            elif ch == ' ':
                if is_after_comma:
                    is_after_comma = False
                else:
                    cur_str += ch
            else:
                cur_str += ch

        # strip the type tag: {"height":0, "width":0}
        keys = [':'.join(k.split(':')[1:]) for k in keys]
        values = [':'.join(v.split(':')[1:]) for v in values]

        obj_dict = {k: v for k, v in zip(keys, values)}
        # # ordinary assignments will be copy-propagated; use a call to avoid that
        # new_obj_func = PandasmInsnArgument('func', '__new_object__')
        # builder.create_call(new_obj_func, [PandasmInsnArgument('object', obj_dict)], label=insn.label)
        builder.create_assign(PandasmInsnArgument('object', obj_dict), label=insn.label)

    @staticmethod
    def newobjrange(insn: NAddressCode, builder: IRBuilder):
        obj = insn.args[3]
        num_args = int(insn.args[2].value, 16) - 1
        args = []
        prev_arg: PandasmInsnArgument = insn.args[3]
        for _ in range(num_args):
            prev_arg = prev_arg.get_next_reg()
            args.append(prev_arg)
        builder.create_call(obj, args, label=insn.label)

    @staticmethod
    def newlexenv(insn: NAddressCode, builder: IRBuilder):
        array_arg = PandasmInsnArgument('array', [PandasmInsnArgument('undefined') for _ in range(int(insn.args[1].value, 16))])

        # since we have no way of knowing statically what level this new lexenv is, we'll just append a random number
        # to its name...
        lexenv_arg = PandasmInsnArgument(f'lexenv_{insn.__hash__()}')
        # and use a special variable 'cur_lexenv_level' to keep track of the level in the IR...
        cur_lexenv_arg = PandasmInsnArgument('cur_lexenv_level', lexenv_arg)
        builder.create_assign(array_arg, lexenv_arg, label=insn.label)
        # assign the new lexenv to acc
        builder.create_assign(lexenv_arg)

        # and finally use a pseudo-function __get_lexenv_level__ to fetch the level and assign it to 'cur_lexenv_level'
        get_lexenv_level_arg = PandasmInsnArgument('func', '__get_lexenv_level__')
        builder.create_call(get_lexenv_level_arg, [lexenv_arg], cur_lexenv_arg)

    @staticmethod
    def add2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='+', label=insn.label)

    @staticmethod
    def sub2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='-', label=insn.label)

    @staticmethod
    def mul2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='*', label=insn.label)

    @staticmethod
    def div2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='/', label=insn.label)

    @staticmethod
    def mod2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='mod', label=insn.label)

    @staticmethod
    def eq(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='==', label=insn.label)

    @staticmethod
    def noteq(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='!=', label=insn.label)

    @staticmethod
    def less(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='<', label=insn.label)

    @staticmethod
    def lesseq(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='<=', label=insn.label)

    @staticmethod
    def greater(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='>', label=insn.label)

    @staticmethod
    def greatereq(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='>=', label=insn.label)

    @staticmethod
    def shl2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='<<', label=insn.label)

    @staticmethod
    def shr2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='>>>', label=insn.label)

    @staticmethod
    def ashr2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='>>', label=insn.label)

    @staticmethod
    def and2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='&', label=insn.label)

    @staticmethod
    def or2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='|', label=insn.label)

    @staticmethod
    def xor2(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='^', label=insn.label)

    @staticmethod
    def exp(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='**', label=insn.label)

    @staticmethod
    def typeof(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_uop(PandasmInsnArgument('acc'), rhs_op='typeof', label=insn.label)

    @staticmethod
    def tonumber(insn: NAddressCode, builder: IRBuilder):
        builder.create_call(PandasmInsnArgument('func', '__ToNumber__'), [PandasmInsnArgument('acc')], label=insn.label)

    @staticmethod
    def tonumeric(insn: NAddressCode, builder: IRBuilder):
        builder.create_call(PandasmInsnArgument('func', '__ToNumeric__'), [PandasmInsnArgument('acc')], label=insn.label)

    @staticmethod
    def neg(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_uop(PandasmInsnArgument('acc'), rhs_op='-', label=insn.label)

    @staticmethod
    def not_(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_uop(PandasmInsnArgument('acc'), rhs_op='~', label=insn.label)

    @staticmethod
    def inc(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(PandasmInsnArgument('acc'), PandasmInsnArgument('imm', '0x1'), rhs_op='+', label=insn.label)

    @staticmethod
    def dec(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(PandasmInsnArgument('acc'), PandasmInsnArgument('imm', '0x1'), rhs_op='-', label=insn.label)

    @staticmethod
    def istrue(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[1], PandasmInsnArgument('true'), rhs_op='==', label=insn.label)

    @staticmethod
    def isfalse(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[1], PandasmInsnArgument('false'), rhs_op='==', label=insn.label)

    @staticmethod
    def isin(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='in', label=insn.label)

    @staticmethod
    def instanceof(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[2], PandasmInsnArgument('acc'), rhs_op='instanceof', label=insn.label)

    @staticmethod
    def strictnoteq(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[1], insn.args[3], rhs_op='!==', label=insn.label)

    @staticmethod
    def stricteq(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign_rhs_bop(insn.args[1], insn.args[3], rhs_op='===', label=insn.label)

    @staticmethod
    def callarg0(insn: NAddressCode, builder: IRBuilder):
        # insn.args[0] and [1] are both acc, i.e. this instruction assumes "acc = acc(xxx)"
        # same for other callargx instructions
        args = [PandasmInsnArgument('FunctionObject'), PandasmInsnArgument('NewTarget')]
        builder.create_call(PandasmInsnArgument('acc'), args, label=insn.label)

    @staticmethod
    def callarg1(insn: NAddressCode, builder: IRBuilder):
        args = [PandasmInsnArgument('FunctionObject'), PandasmInsnArgument('NewTarget'), insn.args[3]]
        builder.create_call(PandasmInsnArgument('acc'), args, label=insn.label)

    @staticmethod
    def callargs2(insn: NAddressCode, builder: IRBuilder):
        args = [PandasmInsnArgument('FunctionObject'), PandasmInsnArgument('NewTarget'), insn.args[3], insn.args[4]]
        builder.create_call(PandasmInsnArgument('acc'), args, label=insn.label)

    @staticmethod
    def callargs3(insn: NAddressCode, builder: IRBuilder):
        args = [PandasmInsnArgument('FunctionObject'), PandasmInsnArgument('NewTarget'), insn.args[3], insn.args[4], insn.args[5]]
        builder.create_call(PandasmInsnArgument('acc'), args, label=insn.label)

    @staticmethod
    def callthis0(insn: NAddressCode, builder: IRBuilder):
        # insn.args[0] and [1] are both acc, i.e. this instruction assumes "acc = acc(xxx)"
        # same for other callthisx instructions
        args = [PandasmInsnArgument('FunctionObject'), PandasmInsnArgument('NewTarget'), insn.args[3]]
        builder.create_call(PandasmInsnArgument('acc'), args, label=insn.label)

    @staticmethod
    def callthis1(insn: NAddressCode, builder: IRBuilder):
        args = [PandasmInsnArgument('FunctionObject'), PandasmInsnArgument('NewTarget'), insn.args[3], insn.args[4]]
        builder.create_call(PandasmInsnArgument('acc'), args, label=insn.label)

    @staticmethod
    def callthis2(insn: NAddressCode, builder: IRBuilder):
        args = [
            PandasmInsnArgument('FunctionObject'), PandasmInsnArgument('NewTarget'),
            insn.args[3], insn.args[4], insn.args[5]
        ]
        builder.create_call(PandasmInsnArgument('acc'), args, label=insn.label)

    @staticmethod
    def callthis3(insn: NAddressCode, builder: IRBuilder):
        args = [
            PandasmInsnArgument('FunctionObject'), PandasmInsnArgument('NewTarget'),
            insn.args[3], insn.args[4], insn.args[5], insn.args[6]
        ]
        builder.create_call(PandasmInsnArgument('acc'), args, label=insn.label)

    @staticmethod
    def callthisrange(insn: NAddressCode, builder: IRBuilder):
        num_actual_args = int(insn.args[3].value, 16)
        actual_args = [insn.args[4]]
        prev_arg: PandasmInsnArgument = actual_args[0]
        for _ in range(num_actual_args):
            prev_arg = prev_arg.get_next_reg()
            actual_args.append(prev_arg)

        args = [
            PandasmInsnArgument('FunctionObject'), PandasmInsnArgument('NewTarget'),
            *actual_args
        ]
        builder.create_call(PandasmInsnArgument('acc'), args, label=insn.label)

    @staticmethod
    def supercallthisrange(insn: NAddressCode, builder: IRBuilder):
        num_actual_args = int(insn.args[2].value, 16)
        if num_actual_args == 0:
            actual_args = []
        else:
            actual_args = [insn.args[3]]
            prev_arg: PandasmInsnArgument = actual_args[0]
            for _ in range(num_actual_args-1):
                prev_arg = prev_arg.get_next_reg()
                actual_args.append(prev_arg)

        args = [
            PandasmInsnArgument('FunctionObject'), PandasmInsnArgument('NewTarget'),
            *actual_args
        ]
        builder.create_call(PandasmInsnArgument('func', 'super'), args, label=insn.label)

    @staticmethod
    def definefunc(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(insn.args[2], label=insn.label)

    @staticmethod
    def definemethod(insn: NAddressCode, builder: IRBuilder):
        homeobject = PandasmInsnArgument("field", "[HomeObject]", insn.args[2])
        builder.create_assign(insn.args[0], homeobject, label=insn.label)
        builder.create_assign(insn.args[2])

    @staticmethod
    def defineclasswithbuffer(insn: NAddressCode, builder: IRBuilder):
        define_class_arg = PandasmInsnArgument('func', '__define_class__')
        class_ctor = insn.args[2]
        superclass = insn.args[5]
        comment = f'class methods: {insn.args[3].value}'
        builder.create_call(define_class_arg, [class_ctor, superclass], label=insn.label, comment=comment)

    @staticmethod
    def ldlexvar(insn: NAddressCode, builder: IRBuilder):
        # since we have no way of knowing statically what the current level of lexenv is, we'll use
        # a pseudo-function __get_lexenv__ to represent the action of loading lexenv relative to
        # the current level of lexenv
        get_lexenv_arg = PandasmInsnArgument('func', '__get_lexenv__')
        lexenv_arg = PandasmInsnArgument('lexenv')
        cur_lexenv_arg = PandasmInsnArgument('cur_lexenv_level', lexenv_arg)
        builder.create_call(get_lexenv_arg, [cur_lexenv_arg, insn.args[1]], lexenv_arg, label=insn.label)
        lexvar_arg = PandasmInsnArgument('field', insn.args[2], arg_ref_obj=lexenv_arg)
        builder.create_assign(lexvar_arg)

    @staticmethod
    def stlexvar(insn: NAddressCode, builder: IRBuilder):
        get_lexenv_arg = PandasmInsnArgument('func', '__get_lexenv__')
        lexenv_arg = PandasmInsnArgument('lexenv')
        cur_lexenv_arg = PandasmInsnArgument('cur_lexenv_level', lexenv_arg)
        builder.create_call(get_lexenv_arg, [cur_lexenv_arg, insn.args[0]], lexenv_arg, label=insn.label)
        lexvar_arg = PandasmInsnArgument('field', insn.args[1], arg_ref_obj=lexenv_arg)
        builder.create_assign(PandasmInsnArgument('acc'), lexvar_arg)

    @staticmethod
    def lda_str(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(insn.args[1], label=insn.label)

    @staticmethod
    def tryldglobalbyname(insn: NAddressCode, builder: IRBuilder):
        assert_defined_arg = PandasmInsnArgument('func', '__assert_defined__')
        insn.args[2].value = insn.args[2].value.strip('"')  # for better readability, strip the enclosing quotes
        builder.create_call(assert_defined_arg, [insn.args[2]], label=insn.label)
        builder.create_assign(insn.args[2])

    @staticmethod
    def ldobjbyname(insn: NAddressCode, builder: IRBuilder):
        insn.args[2].set_ref_obj(insn.args[0])
        builder.create_assign(insn.args[2], insn.args[0], label=insn.label)

    @staticmethod
    def stobjbyname(insn: NAddressCode, builder: IRBuilder):
        insn.args[2].set_ref_obj(insn.args[3])
        builder.create_assign(insn.args[0], insn.args[2], label=insn.label)

    @staticmethod
    def mov(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(insn.args[1], insn.args[0], label=insn.label)

    @staticmethod
    def jmp(insn: NAddressCode, builder: IRBuilder):
        builder.create_uncond_jump(insn.args[0], label=insn.label)

    @staticmethod
    def jeqz(insn: NAddressCode, builder: IRBuilder):
        builder.create_cond_jump(insn.args[0], PandasmInsnArgument('zero'), '==', insn.args[1], label=insn.label)

    @staticmethod
    def jnez(insn: NAddressCode, builder: IRBuilder):
        builder.create_cond_jump(insn.args[0], PandasmInsnArgument('zero'), '!=', insn.args[1], label=insn.label)

    @staticmethod
    def lda(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(insn.args[1], label=insn.label)

    @staticmethod
    def sta(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(insn.args[0], insn.args[1], label=insn.label)

    @staticmethod
    def ldai(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(insn.args[1], label=insn.label)

    @staticmethod
    def return_(insn: NAddressCode, builder: IRBuilder):
        builder.create_return(label=insn.label)

    @staticmethod
    def returnundefined(insn: NAddressCode, builder: IRBuilder):
        builder.create_return(PandasmInsnArgument('undefined'), label=insn.label)

    @staticmethod
    def poplexenv(insn: NAddressCode, builder: IRBuilder):
        cur_lexenv_arg = PandasmInsnArgument('cur_lexenv_level', '')
        builder.create_assign_rhs_bop(cur_lexenv_arg, PandasmInsnArgument('imm', '1'), cur_lexenv_arg, '-', label=insn.label)

    @staticmethod
    def ldhole(insn: NAddressCode, builder: IRBuilder):
        builder.create_assign(PandasmInsnArgument('hole'), label=insn.label)

    @staticmethod
    def stownbyname(insn: NAddressCode, builder: IRBuilder):
        insn.args[2].set_ref_obj(insn.args[3])
        builder.create_assign(insn.args[0], insn.args[2], label=insn.label)

    @staticmethod
    def ldexternalmodulevar(insn: NAddressCode, builder: IRBuilder):
        external_module_no = int(insn.args[1].value, 16)
        class_name = insn.parent_block.parent_method.parent_class.name
        this_module = insn.parent_block.parent_method.parent_class.parent_module
        external_module_name = this_module.ctx.module_requests[class_name][external_module_no]

        regular_import = external_module_name['regular_import']
        import_name = PandasmInsnArgument('module', regular_import.import_name)
        local_name = PandasmInsnArgument('module', regular_import.local_name)
        requested_module = PandasmInsnArgument('module', external_module_name['requested_module'])
        builder.create_import(import_name, local_name, requested_module, label=insn.label)
        builder.create_assign(PandasmInsnArgument('module', regular_import.local_name))

    @staticmethod
    def asyncfunctionenter(insn: NAddressCode, builder: IRBuilder):
        builder.create_call(PandasmInsnArgument('func', 'AsyncFunction'), [], label=insn.label)

    @staticmethod
    def newlexenvwithname(insn: NAddressCode, builder: IRBuilder):
        array_arg = PandasmInsnArgument('litarr',
                                        insn.args[2])

        # since we have no way of knowing statically what level this new lexenv is, we'll just append a random number
        # to its name...
        lexenv_arg = PandasmInsnArgument(f'lexenv_{insn.__hash__()}')
        # and use a special variable 'cur_lexenv_level' to keep track of the level in the IR...
        cur_lexenv_arg = PandasmInsnArgument('cur_lexenv_level', lexenv_arg)
        builder.create_assign(array_arg, lexenv_arg, label=insn.label)
        # assign the new lexenv to acc
        builder.create_assign(lexenv_arg)

        # and finally use a pseudo-function __get_lexenv_level__ to fetch the level and assign it to 'cur_lexenv_level'
        get_lexenv_level_arg = PandasmInsnArgument('func', '__get_lexenv_level__')
        builder.create_call(get_lexenv_level_arg, [lexenv_arg], cur_lexenv_arg)

    @staticmethod
    def resumegenerator(insn: NAddressCode, builder: IRBuilder):
        generator_func = PandasmInsnArgument('acc')
        builder.create_call(PandasmInsnArgument('func', '__GeneratorResume__'), [generator_func], label=insn.label)

    @staticmethod
    def getresumemode(insn: NAddressCode, builder: IRBuilder):
        generator_func = PandasmInsnArgument('acc')
        builder.create_call(PandasmInsnArgument('func', '__get_resume_mode__'), [generator_func], label=insn.label)

    @staticmethod
    def suspendgenerator(insn: NAddressCode, builder: IRBuilder):
        value = PandasmInsnArgument('acc')
        generator_func = insn.args[1]
        builder.create_call(PandasmInsnArgument('func', '__GeneratorSuspend__'), [value, generator_func], label=insn.label)

    @staticmethod
    def asyncfunctionawaituncaught(insn: NAddressCode, builder: IRBuilder):
        await_expr = PandasmInsnArgument('acc')
        async_func = insn.args[1]
        builder.create_call(PandasmInsnArgument('func', '__await__'), [async_func, await_expr], label=insn.label)

    @staticmethod
    def asyncfunctionresolve(insn: NAddressCode, builder: IRBuilder):
        resolve_func = PandasmInsnArgument('field', '"resolve"')
        promise = PandasmInsnArgument('module', 'Promise')
        resolve_func.set_ref_obj(promise)
        resolve_value = PandasmInsnArgument('acc')
        builder.create_call(resolve_func, [resolve_value], label=insn.label)

    @staticmethod
    def asyncfunctionreject(insn: NAddressCode, builder: IRBuilder):
        resolve_func = PandasmInsnArgument('field', '"reject"')
        promise = PandasmInsnArgument('module', 'Promise')
        resolve_func.set_ref_obj(promise)
        resolve_value = PandasmInsnArgument('acc')
        builder.create_call(resolve_func, [resolve_value], label=insn.label)

    @staticmethod
    def definefieldbyname(insn: NAddressCode, builder: IRBuilder):
        insn.args[2].set_ref_obj(insn.args[3])
        builder.create_assign(insn.args[0], insn.args[2], label=insn.label)

    @staticmethod
    def throw(insn: NAddressCode, builder: IRBuilder):
        builder.create_uncond_throw(PandasmInsnArgument('acc'), label=insn.label)

    @staticmethod
    def throw_ifsupernotcorrectcall(insn: NAddressCode, builder: IRBuilder):
        is_super_correctly_called_arg = PandasmInsnArgument('func', '__is_super_correctly_called__')
        tmp_retval = PandasmInsnArgument('tmp', 'tmp0')
        builder.create_call(is_super_correctly_called_arg, [PandasmInsnArgument('acc')], tmp_retval, label=insn.label)
        exception = insn.args[1]
        builder.create_cond_throw(tmp_retval, PandasmInsnArgument('false'), '==', exception)

    @staticmethod
    def throw_undefinedifholewithname(insn: NAddressCode, builder: IRBuilder):
        is_hole_arg = PandasmInsnArgument('func', '__is_hole__')
        tmp_retval = PandasmInsnArgument('tmp', 'tmp0')
        builder.create_call(is_hole_arg, [PandasmInsnArgument('acc')], tmp_retval, label=insn.label)
        exception = PandasmInsnArgument('str', f"'Value of {insn.args[1]} is undefined'")
        builder.create_cond_throw(tmp_retval, PandasmInsnArgument('true'), '==', exception)
