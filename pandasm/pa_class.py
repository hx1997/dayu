import typing

from pandasm.field import PandasmField
from pandasm.method import PandasmMethod


class PandasmClass:
    def __init__(self, name):
        self.name = name
        self.methods: typing.List[PandasmMethod] = []
        self.fields: typing.List[PandasmField] = []
