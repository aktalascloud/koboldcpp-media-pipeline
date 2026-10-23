"""Trusted bench-only CPU op: preserve original Torch unstable tie order exactly."""
import numpy as np
import torch
import importlib
import importlib.machinery
import sys
import types
from pathlib import Path

# Version0.14's public initializer eagerly imports unrelated tokenizer converters
# and requires Transformers. Load its unchanged trusted core as a namespace;
# this experiment uses only the documented PythonOp registration layer.
if 'onnxruntime_extensions' not in sys.modules:
    directory=Path(__file__).resolve().parent/'deps/onnxruntime_extensions'
    package=types.ModuleType('onnxruntime_extensions')
    package.__path__=[str(directory)]
    package.__spec__=importlib.machinery.ModuleSpec('onnxruntime_extensions',loader=None,is_package=True)
    package.__spec__.submodule_search_locations=package.__path__
    sys.modules['onnxruntime_extensions']=package
core=importlib.import_module('onnxruntime_extensions._ocos')
onnx_op=core.Opdef.declare
PyCustomOpDef=core.PyCustomOpDef
get_library_path=core.get_library_path
enable_py_op=core.enable_py_op

COUNTS={'calls':0}
CAPTURE_IDS=None
enable_py_op(True)


@onnx_op(op_type='ATDOriginalSort',inputs=[PyCustomOpDef.dt_int64],
         outputs=[PyCustomOpDef.dt_int64,PyCustomOpDef.dt_int64],
         attrs={'axis':PyCustomOpDef.dt_int64,'descending':PyCustomOpDef.dt_int64})
def original_sort(values,**attributes):
    assert torch.version.cuda is None
    tensor=torch.from_numpy(np.array(values,dtype=np.int64,copy=True))
    if CAPTURE_IDS is not None:CAPTURE_IDS.append(np.array(values,copy=True))
    result=torch.sort(tensor,dim=int(attributes['axis']),descending=bool(attributes['descending']),stable=False)
    COUNTS['calls']+=1
    return result.values.numpy(),result.indices.numpy()


def register_symbolic():
    from torch.onnx import symbolic_helper as sh
    def symbolic(graph,value,*args):
        if len(args)==3:
            stable,dim,descending=args
            if sh._parse_arg(stable,'b'):
                raise ValueError('This op preserves original stable=False only')
        elif len(args)==2:
            dim,descending=args
        else:
            raise ValueError('Unexpected aten::sort schema')
        if value.type().scalarType()!='Long':
            raise ValueError('ATD category IDs must be int64')
        axis=sh._parse_arg(dim,'i');largest=int(sh._parse_arg(descending,'b'))
        sorted_values,indices=graph.op('ai.onnx.contrib::ATDOriginalSort',value,
                                      axis_i=axis,descending_i=largest,outputs=2)
        sorted_values.setType(value.type());indices.setType(value.type())
        return sorted_values,indices
    torch.onnx.register_custom_op_symbolic('aten::sort',symbolic,18)


def register_runtime(options):
    options.register_custom_ops_library(get_library_path())
    return get_library_path()
