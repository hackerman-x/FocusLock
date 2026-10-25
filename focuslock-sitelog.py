#!/usr/bin/env python3
"""FocusLock site logger: counts attempts to open blocked websites.

During a lock, focuslock-apply.sh points every blocked site at ADDR in
/etc/hosts and runs this as a systemd service (a root-owned copy in
/usr/local/sbin, with no privilege beyond binding ports 80/443 and a
read-only system). A browser opening a blocked site connects here instead of
the real server; this reads only the site's name -- the SNI in the HTTPS
handshake, or the HTTP Host header -- appends "<epoch>\\t<host>" to LOG, and
closes the connection. It never sends anything back, so the site stays
blocked; and if this isn't running, the connection is just refused, so
blocking never depends on it.

Only blocked sites resolve to ADDR, so only blocked sites are ever logged.
Stdlib only. Exits by itself once the lock has ended.
"""
import argparse
import os
import re
import socket
import struct
import threading
import time

ADDR = "127.83.76.1"
HTTP_PORT, TLS_PORT = 80, 443
LOG = "/var/lib/focuslock-sitelog/attempts.log"
LOCK_FILE = "/etc/focuslock/unlock_at"
MAX_LOG_BYTES = 1_000_000
MAX_CLIENTS = 32
READ_LIMIT = 16 * 1024
TIMEOUT = 3.0
HOST_RE = re.compile(r"^(?=.{1,253}$)[a-z0-9-]+(\.[a-z0-9-]+)+$")

_log_lock = threading.Lock()
_slots = threading.BoundedSemaphore(MAX_CLIENTS)


def sni_from_client_hello(data):
    """The server name in a TLS ClientHello, or None. Never raises."""
    try:
        if len(data) < 5 or data[0] != 0x16:
            return None
        pos = 5
        if data[pos] != 0x01:                      # handshake type: ClientHello
            return None
        pos += 4 + 2 + 32                          # type+length, client_version, random
        pos += 1 + data[pos]                       # session id
        pos += 2 + struct.unpack_from("!H", data, pos)[0]   # cipher suites
        pos += 1 + data[pos]                       # compression methods
        end = pos + 2 + struct.unpack_from("!H", data, pos)[0]
        pos += 2
        while pos + 4 <= min(end, len(data)):
            ext_type, ext_len = struct.unpack_from("!HH", data, pos)
            pos += 4
            if ext_type == 0:                      # server_name
                p = pos + 2                        # server name list length
                while p + 3 <= pos + ext_len:
                    name_type, name_len = data[p], struct.unpack_from("!H", data, p + 1)[0]
                    p += 3
                    if name_type == 0:
                        return clean_host(data[p:p + name_len].decode("ascii", "strict"))
                    p += name_len
                return None
            pos += ext_len
    except (IndexError, struct.error, UnicodeDecodeError):
        return None
    return None


def host_from_http(data):
    """The Host header of an HTTP/1.x request, or None."""
    try:
        head = data.split(b"\r\n\r\n", 1)[0].decode("latin-1")
    except UnicodeDecodeError:
        return None
    for line in head.split("\r\n")[1:]:
        name, _, value = line.partition(":")
        if name.strip().lower() == "host":
            return clean_host(value.strip().rsplit(":", 1)[0] if value.count(":") == 1 else value.strip())
    return None


def clean_host(host):
    host = (host or "").strip().lower().rstrip(".")
    return host if HOST_RE.match(host) else None


def append_log(host, path):
    line = f"{int(time.time())}\t{host}\n".encode("ascii")
    with _log_lock:
        try:
            if os.path.getsize(path) > MAX_LOG_BYTES:   # keep the newer half
                with open(path, "rb") as f:
                    f.seek(-MAX_LOG_BYTES // 2, os.SEEK_END)
                    keep = f.read().split(b"\n", 1)[-1]
                with open(path, "wb") as f:
                    f.write(keep)
        except OSError:
            pass
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)


def read_request(conn, tls):
    """Read just enough to find the name: one full TLS record, or the HTTP headers."""
    data = b""
    deadline = time.monotonic() + TIMEOUT
    while len(data) < READ_LIMIT and time.monotonic() < deadline:
        if tls and len(data) >= 5:
            need = 5 + struct.unpack_from("!H", data, 3)[0]
            if len(data) >= need:
                break
        if not tls and b"\r\n\r\n" in data:
            break
        conn.settimeout(max(0.05, deadline - time.monotonic()))
        try:
            chunk = conn.recv(4096)
        except (socket.timeout, OSError):
            break
        if not chunk:
            break
        data += chunk
    return data


def serve(conn, tls, log_path):
    try:
        data = read_request(conn, tls)
        host = sni_from_client_hello(data) if tls else host_from_http(data)
        if host:
            append_log(host, log_path)
    except OSError:
        pass
    finally:
        conn.close()
        _slots.release()


def bind(addr, port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((addr, port))
    srv.listen(64)
    return srv


def listen(srv, tls, log_path):
    while True:
        conn, _ = srv.accept()
        if not _slots.acquire(blocking=False):
            conn.close()                       # busy: drop it -- it's blocked either way
            continue
        threading.Thread(target=serve, args=(conn, tls, log_path), daemon=True).start()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--addr", default=ADDR)
    ap.add_argument("--http-port", type=int, default=HTTP_PORT)
    ap.add_argument("--tls-port", type=int, default=TLS_PORT)
    ap.add_argument("--log", default=LOG)
    ap.add_argument("--lock-file", default=LOCK_FILE)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    # Bind both first: if a port can't be had, fail now so systemd retries.
    servers = [(bind(args.addr, args.http_port), False), (bind(args.addr, args.tls_port), True)]
    for srv, tls in servers:
        threading.Thread(target=listen, args=(srv, tls, args.log), daemon=True).start()
    while os.path.exists(args.lock_file):      # the lock ended: nothing left to log
        time.sleep(30)


if __name__ == "__main__":
    main()
