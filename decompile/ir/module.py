import typing

from decompile.ir.irclass import IRClass
from decompile.ir.module_ctx import IRModuleContext


class IRModule:
    def __init__(self, name=None):
        self.name = name
        self.classes: typing.List[IRClass] = []
        self.ctx = IRModuleContext(self)

    def insert_class(self, irclass: IRClass):
        self.classes.append(irclass)

    def remove_class(self, irclass: IRClass):
        self.classes.remove(irclass)

    def get_class_by_name(self, class_name):
        for clz in self.classes:
            if clz.name == class_name:
                return clz
        return None
