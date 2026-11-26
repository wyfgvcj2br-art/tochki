"""Native user environment for alternate-logon CI processes; not shipped in the app."""
import ctypes
import os

def restore_user_environment():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    advapi=ctypes.WinDLL('advapi32',use_last_error=True)
    userenv=ctypes.WinDLL('userenv',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    advapi.OpenProcessToken.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_void_p)]
    userenv.CreateEnvironmentBlock.argtypes=[ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p,ctypes.c_bool]
    userenv.DestroyEnvironmentBlock.argtypes=[ctypes.c_void_p]
    token=ctypes.c_void_p();block=ctypes.c_void_p()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(),0x000a,ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not userenv.CreateEnvironmentBlock(ctypes.byref(block),token,False):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            cursor=block.value;values={}
            while True:
                entry=ctypes.wstring_at(cursor)
                if not entry:break
                if not entry.startswith('='):
                    key,value=entry.split('=',1);values[key]=value
                cursor+=(len(entry)+1)*ctypes.sizeof(ctypes.c_wchar)
            os.environ.clear()
            os.environ.update(values)
            os.environ['PYTHONIOENCODING']='utf-8'
        finally:userenv.DestroyEnvironmentBlock(block)
    finally:kernel.CloseHandle(token)
