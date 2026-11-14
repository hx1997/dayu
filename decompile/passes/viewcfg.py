import graphviz

from decompile.ir.method import IRMethod
from decompile.method_pass import MethodPass


class ViewCFG(MethodPass):
    def __init__(self, output_path, view, show_exception_edges=False):
        super().__init__()
        self.output_path = output_path
        self.view = view
        self.show_exception_edges = show_exception_edges

    def run_on_method(self, method: IRMethod):
        dot = graphviz.Digraph(format='png', strict=False)
        if self.show_exception_edges:
            method.rebuild_exception_edges()
        for block in method.blocks:
            dot.node(name=str(block.__hash__()), label='\n'.join([self.format_insn(str(insn)) for insn in block.insns]))

        for block in method.blocks:
            for succ in block.successors:
                dot.edge(tail_name=str(block.__hash__()), head_name=str(succ.__hash__()))
            if self.show_exception_edges:
                for handler in block.exception_successors:
                    dot.edge(
                        tail_name=str(block.__hash__()),
                        head_name=str(handler.__hash__()),
                        style='dashed',
                        label='exception',
                    )

        dot.render(filename=self.output_path, view=self.view)

    def format_insn(self, insn):
        remain = insn
        formatted = ''
        line_max_chars = 120
        while len(remain) > line_max_chars:
            formatted += f'{remain[:line_max_chars]}\n'
            remain = remain[line_max_chars:]
        if remain:
            formatted += f'{remain}'
        return formatted
