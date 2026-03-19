import os
import sys
import ctypes
import socket

# Flags for our namespaces
CLONE_NEWUTS = 0x04000000 # Hostname Isolation
CLONE_NEWPID = 0x20000000 # Process ID Isolation

def unshare(flags):
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.unshare(flags) != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

def run_container():
    print(f"[*] Host process starting... Host PID: {os.getpid()}")
    print("[*] Preparing the PID namespace... (requires sudo)")
    
    try:
        # CRITICAL DIFFERENCE for PID namespaces:
        # We must unshare BEFORE forking! 
        # A process cannot change its own PID namespace. the unshare call dictates
        # that the NEXT child created will be in the new isolated namespace.
        unshare(CLONE_NEWPID | CLONE_NEWUTS)
    except Exception as e:
        print(f"[!] Namespace error! Did you use sudo? Error: {e}")
        sys.exit(1)
        
    # Now we fork. The child is born into the new PID namespace!
    child_pid = os.fork()
    
    if child_pid == 0:
        # Inside the container
        # Since we are the first process in the new PID namespace, our PID here is 1!
        socket.sethostname("super-isolated")
        
        print(f"[*] Child process alive!")
        print(f"[*] According to the container, my PID is magically: {os.getpid()}")
        print("[*] (Hint: If it says 1, we succeeded!)")
        
        os.execv('/bin/sh', ['sh'])
        
    else:
        # Parent simply waits
        print(f"[*] Parent knows the child's REAL PID on the host is: {child_pid}")
        _, status = os.waitpid(child_pid, 0)
        print(f"[*] Child stopped with status {status}.")

if __name__ == "__main__":
    if not hasattr(os, 'fork'):
        print("Error: Needs Linux/WSL!")
        sys.exit(1)
    
    run_container()
