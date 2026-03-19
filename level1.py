import os
import sys
import ctypes
import socket

# This is the Linux kernel flag used to tell unshare() to create a new UTS namespace.
# UTS isolates the hostname and domainname variables.
CLONE_NEWUTS = 0x04000000

def unshare(flags):
    # We load standard C library to access the unshare system call directly
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.unshare(flags) != 0:
        # Grab the error number if it fails (like permission denied)
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

def run_container():
    print(f"[*] Starting container process...")
    print(f"[*] Host Hostname before everything: {socket.gethostname()}")
    
    # Forking exactly like we did in level 0
    child_pid = os.fork()
    
    if child_pid == 0:
        # Inside the child logic
        print(f"[*] We are inside the child! PID: {os.getpid()}")
        
        try:
            # 1. Detach from current UTS namespace
            unshare(CLONE_NEWUTS)
            
            # 2. Set the new hostname for our container
            socket.sethostname("py-contain")
            print(f"[*] Nice! Container Hostname updated to: {socket.gethostname()}")
        except Exception as e:
            # UTS isolation requires superuser privileges inside standard Linux!
            print(f"[!] Oh no, we hit an error setting up namespaces: {e}")
            print(f"[!] Pro-tip: you probably need to run this script with 'sudo'")
            
        # Fire up the shell
        os.execv('/bin/sh', ['sh'])
        
    else:
        # Parent simply waits for the child shell to exit
        _, status = os.waitpid(child_pid, 0)
        print(f"[*] The child process stopped with status {status}.")
        print(f"[*] Hostname in the parent is untouched: {socket.gethostname()}")

if __name__ == "__main__":
    if not hasattr(os, 'fork'):
        print("Error: Remember we need Linux/WSL for these syscalls to work!")
        sys.exit(1)
    
    run_container()
