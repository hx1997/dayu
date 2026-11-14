"""Rules for values that flow through an exceptional path.

If an instruction throws, it has not written its destination yet. When control
enters a handler, the VM puts the exception in acc and keeps other registers
as they were before the failing instruction.
"""
from decompile.ir.expr import ExprArg
from decompile.ir.nac import NAddressCodeType as T
from pandasm.insn import PandasmInsnArgument

ACC = PandasmInsnArgument('acc')


def operator_may_throw(op):
    # These operators do not coerce objects or invoke user code. Arithmetic,
    # loose equality, and ordering still need type information before relaxing.
    return bool(op) and op not in ('!', '===', '!==')


def argument_may_throw(arg, potentially_throwing_operations=None):
    # Direct callers keep the historical conservative behavior; configured
    # decompilation passes can explicitly opt property access out.
    if potentially_throwing_operations is None:
        potentially_throwing_operations = {'property_access'}
    # These operations may fail before the assignment completes, so the
    # destination must still be treated as its old value on the exception path.
    if 'property_access' in potentially_throwing_operations and arg.ref_obj:
        return True
    if arg.type in ('object', 'array'):
        return True
    if isinstance(arg, ExprArg):
        return (arg.expr_type != 'arith' or operator_may_throw(arg.op)
                or any(argument_may_throw(a, potentially_throwing_operations) for a in arg.value))
    return False


def contains_property_access(arg):
    if arg.ref_obj:
        return True
    if isinstance(arg, ExprArg):
        return any(contains_property_access(value) for value in arg.value)
    return False


def may_throw(insn, potentially_throwing_operations=None):
    # Unknown and effectful NACs may throw. Treating them this way keeps the
    # optimizer from deleting work whose failure is observable.
    if insn.type in (T.CALL, T.UNCOND_THROW, T.COND_THROW, T.UNKNOWN, T.IMPORT):
        return True
    if insn.type == T.ASSIGN:
        return (operator_may_throw(insn.op)
                or any(argument_may_throw(a, potentially_throwing_operations) for a in insn.args))
    return False


def handler_live(block, in_block):
    # A handler gets acc from the VM, not from the normal path. Do not keep an
    # old acc assignment alive just because the handler reads acc.
    values = set()
    for handler in block.exception_successors:
        values.update(in_block[handler])
    return values - {ACC}


def live_before(insn, live_after, exception_live, potentially_throwing_operations=None):
    # A throwing instruction can reach the handler before its normal write, so
    # the handler's requirements must be added to the state before this insn.
    live = set(insn.get_uses()) | (live_after - set(insn.get_defs()))
    if may_throw(insn, potentially_throwing_operations):
        live.update(exception_live)
    return live


def exception_definitions(definitions):
    # The throwing instruction has not produced a new acc value yet.
    return {d for d in definitions if ACC not in d.get_defs()}


def exception_copies(copies):
    return type(copies)(c for c in copies if ACC not in c.get_defs() + c.get_uses())
