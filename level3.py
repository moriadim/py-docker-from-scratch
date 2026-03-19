import os
import sys
import ctypes
import socket

# Flags for our namespaces
CLONE_NEWNS  = 0x00020000  # Mount Isolation (The cornerstone of containers)
CLONE_NEWUTS = 0x04000000  # Hostname Isolation
CLONE_NEWPID = 0x20000000  # Process ID Isolation

def unshare(flags):
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.unshare(flags) != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

def run_container():
    # In a real container engine, you would download a filesystem archive (like alpine minirootfs)
    # and extract it into this folder before running.
    rootfs = "./rootfs"
    
    print(f"[*] Host Process starting... Host PID: {os.getpid()}")
    try:
        # We add CLONE_NEWNS. Any mounts or unmounts we do from now on 
        # won't affect the host machine!
        unshare(CLONE_NEWNS | CLONE_NEWPID | CLONE_NEWUTS)
    except Exception as e:
        print(f"[!] Namespace error! Sudo needed? Error: {e}")
        sys.exit(1)
        
    child_pid = os.fork()
    
    if child_pid == 0:
        # --- Inside the Container ---
        socket.sethostname("fs-contain")
        print(f"[*] Container alive! PID inside: {os.getpid()}")
        
        if not os.path.exists(rootfs):
            os.makedirs(rootfs, exist_ok=True)
            print(f"[*] Created an empty folder for rootfs at {rootfs}.")
            print(f"[*] NOTE: True containers extract actual Linux files (like /bin, /lib, /etc) here!")
            
        try:
            # 1. Chroot: Change the apparent root directory for this process and its children!
            # The host's /etc, /bin, /usr etc. are completely gone from our view.
            os.chroot(rootfs)
            
            # Change the current working directory to the new root
            os.chdir("/")
            print("[*] Successfully chroot'ed. The container is now blind to the host's filesystem.")
            
            # 2. Mount /proc: We need to mount the proc pseudo-filesystem so that 
            # tools like 'ps' and 'top' work correctly inside the container.
            if os.path.exists("/proc"):
                libc = ctypes.CDLL("libc.so.6", use_errno=True)
                # Call libc mount function
                libc.mount(b"proc", b"/proc", b"proc", 0, b"")
                print("[*] Successfully mounted /proc virtual filesystem.")
            
        except Exception as e:
            print(f"[!] Filesystem operation failed: {e}")
            
        # 3. Fire up the shell
        try:
            print("[*] Trying to run /bin/sh...")
            os.execv('/bin/sh', ['sh'])
        except FileNotFoundError:
            print("\n[!] CRASH: /bin/sh is missing in our new root!")
            print("[!] Why? Because our rootfs folder is completely empty!")
            print("[!] To fix this: Download an 'alpine minirootfs' tarball online,")
            print("[!] extract it into the ./rootfs directory, and run me again.")
            sys.exit(1)
            
    else:
        # --- Inside the Host (Parent) ---
        _, status = os.waitpid(child_pid, 0)
        print(f"[*] Child stopped with status {status}.")

if __name__ == "__main__":
    if not hasattr(os, 'fork'):
        print("Error: Needs Linux/WSL!")
        sys.exit(1)
    
    run_container()
