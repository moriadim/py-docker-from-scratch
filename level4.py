import os
import sys
import ctypes
import socket
import time

# Namespace Flags
CLONE_NEWNS  = 0x00020000  
CLONE_NEWUTS = 0x04000000  
CLONE_NEWPID = 0x20000000  

def unshare(flags):
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.unshare(flags) != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

def apply_cgroups(pid):
    """
    Limits the resources of the given process ID using Linux Control Groups (cgroups).
    """
    # This path is the standard default for Cgroups v2
    cgroup_dir = "/sys/fs/cgroup/pycontainer"
    print(f"[*] Applying Cgroups limits to PID {pid}...")
    
    try:
        # 1. Creating a new cgroup is literally just creating a folder!
        if not os.path.exists(cgroup_dir):
            os.makedirs(cgroup_dir, exist_ok=True)
            
        # 2. Limit memory to 50MB (prevents the container from starving the host RAM)
        mem_limit_file = os.path.join(cgroup_dir, "memory.max")
        if os.path.exists(mem_limit_file):
            with open(mem_limit_file, "w") as f:
                f.write(str(50 * 1024 * 1024))
                
        # 3. Limit max processes to 20 (prevents 'fork bombs' inside the container)
        pids_max_file = os.path.join(cgroup_dir, "pids.max")
        if os.path.exists(pids_max_file):
            with open(pids_max_file, "w") as f:
                f.write("20")
                
        # 4. Add the child process to this cgroup container
        with open(os.path.join(cgroup_dir, "cgroup.procs"), "w") as f:
            f.write(str(pid))
            
        print("[*] Successfully limited Memory (50MB) and Max Processes (20).")
    except Exception as e:
        print(f"[!] Warning: Cgroups setup failed: {e}")
        print("[!] This usually happens if not root, or if your system uses Cgroups v1 instead of v2.")

def run_container():
    print(f"[*] Host Process starting... Host PID: {os.getpid()}")
    try:
        unshare(CLONE_NEWNS | CLONE_NEWPID | CLONE_NEWUTS)
    except Exception as e:
        print(f"[!] Namespace error! Sudo needed? Error: {e}")
        sys.exit(1)
        
    child_pid = os.fork()
    
    if child_pid == 0:
        # Child Process (Inside container)
        
        # We sleep for a small fraction of a second. Why?
        # To give the Parent process time to write our real PID into the Cgroups 
        # file before we start doing heavy work or messing up our PID via execv.
        time.sleep(0.1)
        
        socket.sethostname("cg-contain")
        rootfs = "./rootfs"
        if not os.path.exists(rootfs):
            os.makedirs(rootfs, exist_ok=True)
            
        try:
            os.chroot(rootfs)
            os.chdir("/")
            if os.path.exists("/proc"):
                libc = ctypes.CDLL("libc.so.6", use_errno=True)
                libc.mount(b"proc", b"/proc", b"proc", 0, b"")
        except Exception:
            pass
            
        try:
            os.execv('/bin/sh', ['sh'])
        except FileNotFoundError:
            print("[!] /bin/sh missing in rootfs. Test inside a real Linux environment with an Alpine rootfs!")
            sys.exit(1)
            
    else:
        # Parent Process (Host)
        # We assign the limit from the Host because the Host knows the child's real PID!
        apply_cgroups(child_pid)
        
        _, status = os.waitpid(child_pid, 0)
        print(f"[*] Child stopped. Exit status: {status}")

if __name__ == "__main__":
    if not hasattr(os, 'fork'):
        print("Error: Needs Linux/WSL!")
        sys.exit(1)
    run_container()
