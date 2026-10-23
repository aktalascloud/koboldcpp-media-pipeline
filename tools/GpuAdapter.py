"""Select a physical DXGI GPU, including when RDP puts software at index0."""
import ctypes as c
from ctypes import wintypes as w
import uuid

class _GUID(c.Structure):_fields_=[('data',c.c_ubyte*16)]
class _LUID(c.Structure):_fields_=[('low',w.DWORD),('high',w.LONG)]
class _DESC(c.Structure):
    _fields_=[('name',c.c_wchar*128),('vendor',w.UINT),('device',w.UINT),('subsystem',w.UINT),('revision',w.UINT),('dedicated',c.c_size_t),('system',c.c_size_t),('shared',c.c_size_t),('luid',_LUID),('flags',w.UINT)]
def _method(pointer,index,result,*args):
    table=c.cast(pointer,c.POINTER(c.POINTER(c.c_void_p))).contents
    return c.WINFUNCTYPE(result,c.c_void_p,*args)(table[index])
def adapters():
    guid=_GUID();c.memmove(c.byref(guid),uuid.UUID('770aae78-f26f-4dba-a829-253c83d1b387').bytes_le,16)
    factory=c.c_void_p();create=c.WinDLL('dxgi.dll').CreateDXGIFactory1;create.argtypes=[c.POINTER(_GUID),c.POINTER(c.c_void_p)];create.restype=c.c_long
    if create(c.byref(guid),c.byref(factory))!=0:raise RuntimeError('Cannot enumerate DXGI adapters')
    rows=[]
    try:
        enum=_method(factory,12,c.c_long,w.UINT,c.POINTER(c.c_void_p))
        for index in range(16):
            adapter=c.c_void_p()
            if enum(factory,index,c.byref(adapter))!=0:break
            try:
                desc=_DESC()
                if _method(adapter,10,c.c_long,c.POINTER(_DESC))(adapter,c.byref(desc))!=0:continue
                rows.append(dict(index=index,name=desc.name,vendor=desc.vendor,device=desc.device,dedicated_bytes=desc.dedicated,software=bool(desc.flags&2) or desc.vendor==0x1414,luid=f'{desc.luid.high&0xffffffff:08x}:{desc.luid.low:08x}'))
            finally:_method(adapter,2,w.ULONG)(adapter)
    finally:_method(factory,2,w.ULONG)(factory)
    return rows
def select_dml_adapter():
    hardware=[row for row in adapters() if not row['software']]
    if not hardware:raise RuntimeError('No physical DirectML GPU; software renderers are deliberately excluded')
    return max(hardware,key=lambda row:row['dedicated_bytes'])
