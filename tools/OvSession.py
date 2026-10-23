"""Small FP32 OpenVINO CPU adapter with the ONNX session methods we use."""
from types import SimpleNamespace
from RuntimePaths import ROOT,dependencies
from pathlib import Path
dependencies()
import openvino as ov
class OvSession:
    def __init__(self,path,threads=10):
        self.core=ov.Core()
        config={'PERFORMANCE_HINT':'LATENCY','NUM_STREAMS':1,'INFERENCE_NUM_THREADS':int(threads),'INFERENCE_PRECISION_HINT':'f32'}
        if Path(path).stem.lower().startswith('gpen_'):
            cache=ROOT/'runtime'/'cache'/'openvino';cache.mkdir(parents=True,exist_ok=True)
            self.model=self.core.compile_model(str(path),'CPU',{**config,'CACHE_DIR':str(cache)})
        else:
            model=self.core.read_model(str(path))
            if len(model.outputs)>1:model=ov.Model([model.outputs[0]],model.get_parameters(),model.get_friendly_name())
            self.model=self.core.compile_model(model,'CPU',config)
        self.loaded_from_cache=bool(self.model.get_property('LOADED_FROM_CACHE'))
        self.inputs=[]
        for item in self.model.inputs:
            shape=[d.get_length() if d.is_static else None for d in item.partial_shape]
            kind='tensor(double)' if str(item.element_type)=='<Type: \'double64\'>' or item.element_type==ov.Type.f64 else 'tensor(float)'
            self.inputs.append(SimpleNamespace(name=item.any_name,type=kind,shape=shape))
        self.output=SimpleNamespace(name=self.model.output(0).any_name)
    def get_inputs(self):return self.inputs
    def get_outputs(self):return [self.output]
    def get_providers(self):return ['OpenVINOExecutionProvider:CPU:FP32']
    def run(self,names,feed):return [self.model(feed)[0]]
