"""Optional one-time pinned SA3 CPU build; no models, second Python or global changes."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,urllib.request,zipfile
ROOT=Path(__file__).resolve().parent.parent
COMPILER=('https://github.com/brechtsanders/winlibs_mingw/releases/download/13.2.0posix-18.1.5-11.0.1-msvcrt-r8/winlibs-x86_64-posix-seh-gcc-13.2.0-mingw-w64msvcrt-11.0.1-r8.zip','636865e19b0bcacec55fbbb93f238db4c0ecce72107157329fc3d6a6afc5d1b7')
SOURCES=[('sa3','https://codeload.github.com/betweentwomidnights/sa3.cpp/zip/602af56e411bbff7a4140895cc906b76cfc5a74a','d06b3a615b8dc200a395afc3684aca5200c1f56ed78626ff014f4b0047cd1ec0'),('ggml','https://codeload.github.com/ggml-org/ggml/zip/b77ae790e628270af46a8af1eca38441c23f1252','289ca233db809079b646442df65e8dbb135ac85ea72143815027cee3f398f0f3')]
def unpack(url,digest,target,archive):
    archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.is_file():urllib.request.urlretrieve(url,archive)
    with archive.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    if actual!=digest:raise RuntimeError('SFX source/toolchain hash mismatch')
    target.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for row in z.infolist():
            if not (target/row.filename).resolve().is_relative_to(target.resolve()) or (row.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe SFX build ZIP')
        z.extractall(target)
def prepare():
    out=ROOT/'runtime/sa3'
    if (out/'sa3-generate.exe').is_file():print('Existing portable SFX runtime preserved.');return
    if os.name!='nt':raise RuntimeError('This SFX build recipe targets Windows Haswell/AVX2')
    cache=ROOT/'runtime/cache/sfx-build';cache.mkdir(parents=True,exist_ok=True)
    compiler=ROOT/'build/toolchain/winlibs/mingw64/bin'
    if not (compiler/'gcc.exe').is_file():
        compiler=cache/'compiler/mingw64/bin'
        if not (compiler/'gcc.exe').is_file():unpack(*COMPILER,cache/'compiler',cache/'compiler.zip')
    for role,url,digest in SOURCES:
        parent=cache/role
        if not parent.is_dir():unpack(url,digest,parent,cache/(role+'.zip'))
    source=next((cache/'sa3').glob('sa3.cpp-*'));ggml=source/'ggml'
    if not (ggml/'CMakeLists.txt').exists():
        if ggml.exists() and any(ggml.iterdir()):raise RuntimeError('Unexpected ggml source preserved')
        shutil.copytree(next((cache/'ggml').glob('ggml-*')),ggml,dirs_exist_ok=True)
    p=ggml/'src/ggml-cpu/ggml-cpu.c';s=p.read_text(encoding='utf-8');s=s.replace('#if _WIN32_WINNT >= 0x0602\n        THREAD_POWER_THROTTLING_STATE','#if _WIN32_WINNT >= 0x0602 && defined(THREAD_POWER_THROTTLING_CURRENT_VERSION)\n        THREAD_POWER_THROTTLING_STATE');p.write_text(s,encoding='utf-8')
    deps=cache/'python-build-deps'
    if not list(deps.glob('**/cmake.exe')) or not list(deps.glob('**/ninja.exe')):
        from SetupPro import fetch
        pip=json.loads((ROOT/'tools/pro-setup-sources.json').read_text())['pip'];wheel=cache/pip['name'];fetch(pip,wheel)
        subprocess.run([sys.executable,str(ROOT/'tools/SetupPro.py'),'_pip',str(wheel),'install','--target',str(deps),'cmake==3.31.6','ninja==1.11.1.4'],check=True)
    cmake=next(deps.glob('**/cmake.exe'));ninja=next(deps.glob('**/ninja.exe'));build=cache/'objects'
    flags='-O3 -march=haswell -mtune=haswell -mstackrealign'
    env={**os.environ,'PATH':str(compiler)+os.pathsep+os.environ.get('PATH','')}
    subprocess.run([str(cmake),'-S',str(source),'-B',str(build),'-G','Ninja','-DCMAKE_MAKE_PROGRAM='+str(ninja),'-DCMAKE_C_COMPILER='+str(compiler/'gcc.exe'),'-DCMAKE_CXX_COMPILER='+str(compiler/'g++.exe'),'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_FLAGS='+flags,'-DCMAKE_CXX_FLAGS='+flags,'-DCMAKE_EXE_LINKER_FLAGS=-static-libgcc -static-libstdc++','-DBUILD_SHARED_LIBS=OFF','-DSA3_CUDA=OFF','-DSA3_VULKAN=OFF','-DSA3_METAL=OFF','-DSA3_HIP=OFF','-DGGML_NATIVE=OFF','-DGGML_AVX2=ON','-DGGML_AVX512=OFF','-DGGML_FMA=ON','-DGGML_F16C=ON','-DGGML_BACKEND_DL=OFF','-DBUILD_TESTING=OFF'],env=env,check=True)
    subprocess.run([str(cmake),'--build',str(build),'--target','sa3-generate','-j','4'],env=env,check=True)
    out.mkdir(parents=True,exist_ok=True);shutil.copy2(build/'bin/sa3-generate.exe',out/'sa3-generate.exe')
    for name in ('libgomp-1.dll','libwinpthread-1.dll','libgcc_s_seh-1.dll','libstdc++-6.dll','libdl.dll'):
        if (compiler/name).is_file():shutil.copy2(compiler/name,out/name)
    for src,name in [(source/'LICENSE','SA3-LICENSE.txt'),(ggml/'LICENSE','GGML-LICENSE.txt')]:
        if src.is_file():shutil.copy2(src,out/name)
    (out/'provenance.json').write_text(json.dumps({'backend':'CPU only','source_commits':SOURCES,'compiler':'WinLibs13.2r8 MSVCRT','flags':flags,'source_cache':'runtime/cache/sfx-build','generated_locally':True},indent=2)+'\n',encoding='utf-8')
    print('SFX CPU runtime built locally; model weights remain separate original downloads.')
if __name__=='__main__':prepare()
