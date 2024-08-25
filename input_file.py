import typing


class DecompilerInputFile:
    """
    Abstract base for various types of files dayu decompiler takes as input
    Each type of file should contain enough information (see diagram below) for the decompiler to work with

    Hierarchy diagram:
     -------------------
    |       file       |
    -------------------
             | contains
             v
     --------------------------
    | class A | class B | ... |
    --------------------------
         | contains
         v
     --------------------------------------------------
    |method A.1|method A.2|...|field A.1|field A.2|...|
    --------------------------------------------------
         | contains
         v
     ----------------------------------------
    |instruction A.1.1|instruction A.1.2|...|
    ----------------------------------------
    """
    def __init__(self):
        self.classes = {}
        raise NotImplementedError(f'{self.__class__.__name__}: Use one of the subclasses of DecompilerInputFile instead of this abstract base')

    def iter_classes(self):
        for clz_name, clz in self.classes.items():
            yield clz

    def iter_methods(self, clz):
        for method in clz.methods:
            yield method

    def iter_fields(self, clz):
        for field in clz.fields:
            yield field

    def iter_insns(self, method):
        for insn in method.insns:
            yield insn

    def get_class_by_name(self, name):
        return self.classes[name]
