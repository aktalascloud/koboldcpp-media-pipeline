"""Offline stale protected-PID regression checks; no processes/models started."""
from pathlib import Path
import sys,tempfile,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from BackendSupervisor import BackendSupervisor,WindowsOperations,SupervisorError
class Ops(WindowsOperations):
    def __init__(self,row,occupied=False):self.row=row;self.occupied=occupied
    def process(self,pid):
        error=PermissionError('protected');error.winerror=5;raise error
    def _powershell(self,script):return self.row
    def listeners(self,port):return [99] if self.occupied else []
def main():
    results=[]
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);record=dict(pid=42,created_ticks=100_000_000,executable=str(root/'koboldcpp-nocuda.exe'))
        for name,row,allowed,occupied in [
            ('new_protected_service',dict(pid=42,name='sandbox-service.exe',created_ticks=130_000_000),True,False),
            ('ambiguous_timestamp',dict(pid=42,name='sandbox-service.exe',created_ticks=100_000_001),False,False),
            ('foreign_native',dict(pid=42,name='koboldcpp-nocuda.exe',created_ticks=130_000_000),False,False),
            ('foreign_worker',dict(pid=42,name='python.exe',created_ticks=130_000_000),False,False),
            ('missing_metadata',None,False,False),
            ('occupied_port',dict(pid=42,name='sandbox-service.exe',created_ticks=130_000_000),True,True)]:
            sup=BackendSupervisor.__new__(BackendSupervisor);sup.operations=Ops(row,occupied);sup.root=root;sup.state_file=root/'state.json';sup.profiles={}
            active=dict(worker=record,port=5005);state=dict(active=active,history=[])
            try:
                assert sup._identity_status(record)=='reused_inaccessible' and allowed
                try:
                    sup._retire_dead(state,active)
                    assert not occupied and 'active' not in state
                except SupervisorError as error:
                    assert occupied and error.body['error']['code']=='foreign_listener' and state['active']==active
            except PermissionError:assert not allowed and state['active']==active
            results.append(dict(case=name,passed=True))
    result=dict(ok=True,cases=results,inference_started=False,processes_terminated=False)
    print(json.dumps(result))
if __name__=='__main__':main()
