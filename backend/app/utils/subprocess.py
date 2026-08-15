import subprocess


def run_command(command: str, *, shell: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, shell=shell, text=True, capture_output=True, check=False)
