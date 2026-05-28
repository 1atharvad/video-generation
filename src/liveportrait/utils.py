import os
import subprocess
import sys


def run_subprocess_with_progress(cmd: list, cwd: str | None = None) -> subprocess.CompletedProcess:
    import pty

    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        cmd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        cwd=cwd,
    )
    os.close(slave_fd)

    output_buf: list[bytes] = []
    try:
        while True:
            chunk = os.read(master_fd, 4096)
            if not chunk:
                break
            output_buf.append(chunk)
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    except OSError:
        pass
    finally:
        os.close(master_fd)

    proc.wait()
    combined = b"".join(output_buf).decode("utf-8", errors="replace")
    return subprocess.CompletedProcess(cmd, proc.returncode, combined, combined)
