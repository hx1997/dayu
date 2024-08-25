import graphviz

from decompile.ir.method import IRMethod
from decompile.method_pass import MethodPass


class ViewCFG(MethodPass):
    def __init__(self, output_path, view):
        self.output_path = output_path
        self.view = view

    def run_on_method(self, method: IRMethod):
        dot = graphviz.Digraph(format='png', strict=True)
        for block in method.blocks:
            dot.node(name=str(block.__hash__()), label='\n'.join([self.format_insn(str(insn)) for insn in block.insns]))

        q = [*method.blocks]
        vis = set()
        while len(q) > 0:
            cur = q.pop(0)
            for succ in cur.successors:
                dot.edge(tail_name=str(cur.__hash__()), head_name=str(succ.__hash__()))
                if succ not in vis:
                    q.append(succ)
                    vis.add(succ)

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
