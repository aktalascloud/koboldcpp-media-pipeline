"""Optional original RIFE runtime; no binary/model is mirrored by this project."""
from pathlib import Path
import hashlib,json,zipfile,shutil,ctypes
from SetupPro import fetch
ROOT=Path(__file__).resolve().parent.parent
ARCHIVE={'url':'https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-windows.zip','bytes':431540241,'sha256':'d8e4d772d26cd8006ef0ad0bc82eb191b53c68677d1ae2f42506d74cbbbea606'}
def prepare():
    from VideoRife import available
    if available(ROOT):print('RIFE already available; no download.');return True
    archive=ROOT/'runtime/cache/rife-20221029.zip';fetch(ARCHIVE,archive)
    prefix='rife-ncnn-vulkan-20221029-windows/'
    mapping={'rife-ncnn-vulkan.exe':'runtime/rife/rife-ncnn-vulkan.exe','LICENSE':'runtime/rife/LICENSE','README.md':'runtime/rife/README.md','rife-v4.6/flownet.bin':'DETAILERS/interpolation/rife-v4.6/flownet.bin','rife-v4.6/flownet.param':'DETAILERS/interpolation/rife-v4.6/flownet.param'}
    with zipfile.ZipFile(archive) as z:
        for source,target in mapping.items():
            data=z.read(prefix+source);p=ROOT/target;p.parent.mkdir(parents=True,exist_ok=True)
            if p.exists() and p.read_bytes()!=data:raise RuntimeError('Different existing RIFE file preserved:'+target)
            if not p.exists():p.write_bytes(data)
    buf=ctypes.create_unicode_buffer(32768);ctypes.windll.kernel32.GetSystemDirectoryW(buf,len(buf));vcomp=Path(buf.value)/'vcomp140.dll'
    if vcomp.is_file():
        target=ROOT/'runtime/rife/vcomp140.dll'
        if not target.exists():shutil.copy2(vcomp,target)
    (ROOT/'runtime/rife/NOTICE.txt').write_text('RIFE/ncnn: upstream MIT license included. Downloaded from original nihui release,not mirrored.\nMicrosoft vcomp140 is copied only from the owner\'s installed Windows runtime for private side-by-side use; not redistributed by this project. If absent,install the official MicrosoftVC++runtime to enable optional48FPS.\nhttps://visualstudio.microsoft.com/license-terms/vs2022-cruntime/\n')
    print('RIFE48FPS ready.' if available(ROOT) else 'RIFE optional: MicrosoftVC++runtime is required.24FPS media serving remains available.')
    return available(ROOT)
if __name__=='__main__':prepare()
