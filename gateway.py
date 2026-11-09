import ipaddress
import json
import os
import select
import socket
import subprocess
import time

import msgpack

DIGITS = "0123456789*#"
PBX = str(ipaddress.IPv4Address(os.environ["PBX_IPV4"]))
CONFIG = "/config"
M4_HOST = os.environ.get("M4_PROXY", "127.0.0.1")


def route():
    result = subprocess.run(
        ["ip", "-j", "-4", "route", "get", PBX],
        capture_output=True, text=True, timeout=2,
    )
    if result.returncode:
        return None
    selected = json.loads(result.stdout)[0]
    return selected.get("dev"), selected.get("prefsrc"), selected.get("gateway")


def response_digit(digit):
    with socket.create_connection((M4_HOST, 5001), timeout=1) as rpc:
        rpc.sendall(msgpack.packb([0, 1, "dtmf_received", [ord(digit)]]))
        messages = msgpack.Unpacker(raw=False)
        while chunk := rpc.recv(4096):
            messages.feed(chunk)
            for kind, message_id, error, result in messages:
                if kind == 1 and message_id == 1:
                    if error:
                        raise ValueError(error)
                    return chr(result) if isinstance(result, int) and 0 < result < 128 else ""
    return ""


def events(buffer):
    while b":" in buffer:
        prefix, rest = buffer.split(b":", 1)
        if not prefix.isdigit() or len(prefix) > 6:
            raise ValueError("Invalid Baresip frame length")
        size = int(prefix)
        if len(rest) < size + 1:
            return
        if rest[size] != ord(","):
            raise ValueError("Invalid Baresip frame delimiter")
        del buffer[:len(prefix) + size + 2]
        yield json.loads(rest[:size])
    if len(buffer) > 6:
        raise ValueError("Invalid Baresip frame header")


def connect_control(process):
    for _ in range(30):
        if process.poll() is not None:
            break
        try:
            return socket.create_connection(("127.0.0.1", 4444), timeout=1)
        except OSError:
            time.sleep(0.2)
    raise OSError("Baresip control socket is unavailable")


def run_call_service(process, selected_route):
    with connect_control(process) as control, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as console:
        buffer = bytearray()
        next_route_check = 0.0
        last_send = 0.0
        while process.poll() is None:
            now = time.monotonic()
            if now >= next_route_check:
                if route() != selected_route:
                    print("Network path changed. Re-registering SIP.", flush=True)
                    return
                next_route_check = now + 2
            if not select.select([control], [], [], 0.25)[0]:
                continue
            chunk = control.recv(4096)
            if not chunk:
                return
            buffer.extend(chunk)
            for event in events(buffer):
                digit = event.get("param", "")
                if event.get("type") != "CALL_DTMF_START" or len(digit) != 1 or digit not in DIGITS:
                    continue
                print(f"DTMF received: {digit}", flush=True)
                try:
                    reply = response_digit(digit)
                except (OSError, ValueError) as error:
                    print(f"Arduino sketch RPC failed: {error}", flush=True)
                    continue
                if len(reply) == 1 and reply in DIGITS:
                    time.sleep(max(0, last_send + 0.30 - time.monotonic()))
                    console.sendto(reply.encode("ascii"), ("127.0.0.1", 5555))
                    last_send = time.monotonic()
                    print(f"DTMF submitted to Baresip: {reply}", flush=True)


def main():
    while True:
        selected_route = route()
        if selected_route is None:
            time.sleep(2)
            continue
        print(f"SIP route: {selected_route}", flush=True)
        process = subprocess.Popen(["baresip", "-f", CONFIG], stdin=subprocess.DEVNULL)
        try:
            run_call_service(process, selected_route)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            print(f"SIP service restarting: {error}", flush=True)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        time.sleep(2)


if __name__ == "__main__":
    main()
