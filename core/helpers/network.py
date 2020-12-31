import socket
import subprocess

def is_network_available(host: str, size: int=0) -> bool:
    try:
        output = subprocess.check_output(["ping", "-c1", f"-s{size}", host]).decode()
    except Exception as e:
        return False
    else:
        if "1 received" in output or "1 packets received" in output:
            return True

    return False

def get_host_by_addr(addr: str) -> str:
    try:
        host = socket.gethostbyaddr(addr)[2][0]
    except Exception as e:
        host = None
        
    return host
