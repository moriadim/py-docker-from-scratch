# Python Docker from Scratch

Building a container from scratch using Python, divided into 5 learning levels based on "Rubber-Docker" concepts.

## Level 0: Fork & Exec (Foundation)

This level demonstrates the foundational concept of Linux processes: how a new process is created and how it can execute a different program.

### Architecture Diagram

```mermaid
graph TD;
    A[Parent Process<br>os.fork()] -->|child_pid == 0| B(Child Process)
    A -->|child_pid > 0| C(Parent waits with os.wait)
    B -->|os.execv<br>('/bin/sh')| D[New Program: 'sh']
    D -->|Exit| C
```

### Lessons Learned
- **Forking**: `os.fork()` creates a nearly identical copy of the calling process but doesn't actually copy all memory immediately. It uses "copy-on-write" (CoW) to be highly efficient. It returns `0` in the child process and the child's ID in the parent.
- **Executing**: `os.execv()` replaces the memory space, code, and data of the current process with a new program (in this case, `/bin/sh`). The process ID remains exactly the same, but the executable changes.
- **Kernel Level Context**: When the kernel handles `fork()`, it allocates new entries in the process table and duplicates the necessary task structures (`task_struct` in Linux). When it handles `exec()`, the kernel discards the cloned memory mappings and loads the new executable's memory sections (text, data, bss) from the filesystem. This two-step mechanism (`fork` + `exec`) is the Unix philosophy for process creation, allowing process environment manipulation (like file descriptors and eventually Namespaces/Cgroups) *between* the fork and the exec phase. This is the exact moment where containers hook in to apply isolation!

## Level 1: UTS Namespace (Hostname Isolation)

UTS (UNIX Time-sharing System) namespaces isolate two system identifiers: `nodename` and `domainname` — primarily what we know as the "hostname". By giving a container its own UTS namespace, modifying the hostname from inside the container doesn't alter the main host networking identity.

### Architecture Diagram

```mermaid
graph TD;
    A[Host Namespace<br>Hostname: host-pc] -->|fork| B[Child Process]
    B -->|unshare CLONE_NEWUTS| C[New UTS Namespace]
    C -->|sethostname| D[Container Environment<br>Hostname: py-contain]
    D -->|execv /bin/sh| E[Isolated Shell]
```

### Lessons Learned
- **Namespaces Core Concept**: These are a Linux Kernel feature that partitions kernel resources. One group of processes sees one set of resources, while another group sees a totally different set. It's the illusion of a dedicated machine!
- **unshare() System Call**: This is how we literally detach the current process from the default main namespace and spin up a new isolated one. We hook into the C library's `unshare` via `ctypes`.
- **Privilege Matters**: Calling `unshare` for UTS and trying to change the hostname requires root access (specifically the `CAP_SYS_ADMIN` capability). Without `sudo`, the kernel outright denies the request to prevent malicious programs from messing with network identities.
