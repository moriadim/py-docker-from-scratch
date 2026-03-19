import os
import sys

def main():
    print(f"Parent process: PID {os.getpid()}")
    
    # Check if os.fork is available (it's Unix-specific)
    if not hasattr(os, 'fork'):
        print("Error: os.fork() is only available on Unix/Linux systems.")
        print("To run this containerization script, please use a Linux environment or WSL.")
        sys.exit(1)

    # Forking a new process
    child_pid = os.fork()
    
    if child_pid == 0:
        # Code executed by the child process
        print(f"Child process: PID {os.getpid()}")
        # Replace the current process with 'sh' program
        os.execv('/bin/sh', ['sh'])
    else:
        # Code executed by the parent process
        os.wait() # Wait for the child process to finish
        print("Child process finished.")

if __name__ == "__main__":
    main()
