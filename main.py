import os
import sys
import ctypes
import socket
import argparse
import time

# ==========================================
# 🎨 Visual Feedback (ANSI Colors)
# ==========================================
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log_info(msg):
    print(f"{Colors.BLUE}[INFO] {msg}{Colors.ENDC}")

def log_success(msg):
    print(f"{Colors.GREEN}[SUCCESS] {msg}{Colors.ENDC}")

def log_error(msg):
    print(f"{Colors.RED}[ERROR] {msg}{Colors.ENDC}")

def log_warn(msg):
    print(f"{Colors.YELLOW}[WARNING] {msg}{Colors.ENDC}")

# ==========================================
# 🧬 Linux Namespaces Flags
# ==========================================
CLONE_NEWNS  = 0x00020000  
CLONE_NEWUTS = 0x04000000  
CLONE_NEWPID = 0x20000000  

def unshare(flags):
    """
    🏗️ EDUCATIONAL COMMENT (The Walls):
    The unshare() system call builds the invisible 'walls' around our process.
    By calling this, we detach the process from the host's namespaces.
    - CLONE_NEWUTS: Walls for the Hostname (we can name it whatever).
    - CLONE_NEWPID: Walls for the Processes (we become PID 1 inside).
    - CLONE_NEWNS: Walls for the Filesystem Mounts (our mounts don't leak outside).
    """
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.unshare(flags) != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
        
def parse_memory(mem_str):
    """Converts a string like '100M' to bytes."""
    mem_str = mem_str.upper()
    if mem_str.endswith('M'): return int(mem_str[:-1]) * 1024 * 1024
    if mem_str.endswith('G'): return int(mem_str[:-1]) * 1024 * 1024 * 1024
    return int(mem_str)

def apply_cgroups(pid, memory_str):
    """
    قفاز EDUCATIONAL COMMENT (The Ceiling / Roof):
    Cgroups form the 'ceiling' of our container. While namespaces (The Walls) 
    limit what the container can *see*, cgroups limit what it can *use*.
    We create a folder in /sys/fs/cgroup, set the max limits, and write our 
    target PID into it. If the container tries to break the ceiling, the kernel stops it.
    """
    cgroup_name = f"ech_container_{pid}"
    cgroup_dir = os.path.join("/sys/fs/cgroup", cgroup_name)
    
    log_info(f"Building the ceiling (Cgroups) for PID {pid}...")
    try:
        os.makedirs(cgroup_dir, exist_ok=True)
        mem_bytes = parse_memory(memory_str)
        
        # memory.max is used in Cgroups V2
        with open(os.path.join(cgroup_dir, "memory.max"), "w") as f:
            f.write(str(mem_bytes))
            
        with open(os.path.join(cgroup_dir, "cgroup.procs"), "w") as f:
            f.write(str(pid))
            
        log_success(f"Cgroups applied: Memory capped at {memory_str}.")
        return cgroup_dir
    except Exception as e:
        log_warn(f"Cgroups failed (Requires root/sudo or cgroups v1 compatibility): {e}")
        return None

def cleanup_cgroup(cgroup_dir):
    """
    🧹 EDUCATIONAL COMMENT (Cleanup):
    We don't want to leave trash on the host system! When the container exits,
    its processes die. We can then safely remove the Cgroup folder we created.
    Notice we don't need to manually unmount /proc here because 'Mount Namespaces' 
    (CLONE_NEWNS) guarantee that the container's unmounting/mounting dies with it!
    """
    if cgroup_dir and os.path.exists(cgroup_dir):
        log_info(f"Cleaning up Cgroup: {cgroup_dir}...")
        try:
            os.rmdir(cgroup_dir)
            log_success("Host system remains clean! Cgroups destroyed.")
        except Exception as e:
            log_warn(f"Failed to remove cgroup {cgroup_dir}: {e}")

# ==========================================
# 🚀 Main Container Engine
# ==========================================
def run_container(args):
    command = args.command
    memory = args.memory
    hostname = args.hostname
    
    log_info(f"{Colors.BOLD}Starting ECH Container Engine...{Colors.ENDC}")
    
    try:
        # Build the Walls (Namespaces) before forking so child inherits the PID namespace
        unshare(CLONE_NEWNS | CLONE_NEWPID | CLONE_NEWUTS)
        log_success("Namespaces (Walls) erected successfully.")
    except Exception as e:
        log_error(f"Failed to unshare namespaces: {e}. (Sudo needed!)")
        sys.exit(1)
        
    child_pid = os.fork()
    
    if child_pid == 0:
        # --- Inside the Container (Child Process) ---
        time.sleep(0.1)  # Brief pause to let the parent build the ceiling
        
        socket.sethostname(hostname)
        log_success(f"Container Hostname isolated and set to: {hostname}")
        
        """
        🧱 EDUCATIONAL COMMENT (The Floor):
        chroot creates the 'floor' or the foundation. It traps the process 
        in a specific directory (./rootfs), making it believe that this directory 
        is the actual root (/) of the OS. The host's true files are totally hidden.
        """
        rootfs = "./rootfs"
        if not os.path.exists(rootfs):
            os.makedirs(rootfs, exist_ok=True)
            log_warn(f"Created empty rootfs at {rootfs}.")
            
        try:
            os.chroot(rootfs)
            os.chdir("/")
            log_success(f"Chroot (Floor) set to {rootfs}.")
            
            # Mount /proc so 'ps' inside container works
            if os.path.exists("/proc"):
                libc = ctypes.CDLL("libc.so.6", use_errno=True)
                # Ensure the container has its own /proc view
                # The kernel automatically unmounts this when the namespace dies!
                libc.mount(b"proc", b"/proc", b"proc", 0, b"")
                log_success("Mounted /proc seamlessly inside container.")
        except Exception as e:
            log_error(f"Filesystem setup failed: {e}")
            
        log_info(f"Executing command: '{command}'")
        cmd_args = command.split()
        try:
            os.execv(cmd_args[0], cmd_args)
        except OSError as e:
            log_error(f"Execution failed: {e}")
            print(f"\n{Colors.YELLOW}---> 💡 ECH Pro Tip: Ensure the Alpine rootfs is actually extracted inside ./rootfs!{Colors.ENDC}")
            sys.exit(1)
            
    else:
        # --- Inside the Host (Parent Process) ---
        cgroup_dir = apply_cgroups(child_pid, memory)
        
        # Wait for the container to exit
        _, status = os.waitpid(child_pid, 0)
        log_info(f"Container exited with status {status}.")
        
        # Run cleanup procedures
        cleanup_cgroup(cgroup_dir)
        log_success(f"{Colors.BOLD}ECH Container Engine shutdown gracefully. See you next time!{Colors.ENDC}")

# ==========================================
# 💻 CLI Interface
# ==========================================
if __name__ == "__main__":
    if not hasattr(os, 'fork'):
        log_error("This script requires a Linux kernel (or WSL) to operate.")
        sys.exit(1)
        
    # User-Friendly argument parser
    parser = argparse.ArgumentParser(description=f"{Colors.BLUE}ECH Container Engine - A Docker-like CLI built from scratch.{Colors.ENDC}")
    subparsers = parser.add_subparsers(dest="action", help="Action to perform (e.g., run)")
    
    # "run" Command
    run_parser = subparsers.add_parser("run", help="Run a command in a new container")
    run_parser.add_argument("command", help="The command to execute (e.g., /bin/sh)")
    run_parser.add_argument("--memory", default="50M", help="Memory limit (e.g., 50M, 1G). Default: 50M")
    run_parser.add_argument("--hostname", default="ech-container", help="Container hostname. Default: ech-container")
    
    args = parser.parse_args()
    
    if args.action == "run":
        run_container(args)
    else:
        parser.print_help()
