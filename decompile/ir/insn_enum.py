import json
import os.path

from decompile.ir.insn_lifter import InsnLifter

mnemonic2lifter_map = {lifter[0].strip('_').replace('_', '.'): lifter[1]
                       for lifter in InsnLifter.__dict__.items() if not lifter[0].startswith('__')}

isa_json_path = os.path.join(os.path.dirname(__file__), '..', 'isa.json')
with open(isa_json_path, 'r', encoding='utf8') as f:
    mnemonic2isainfo_map = json.load(f)
