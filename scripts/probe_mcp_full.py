import json, subprocess, threading, time, queue, sys

p = subprocess.Popen([sys.executable, "-m", "aec_copilot.mcp_full"],
    cwd=".", stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, bufsize=1, encoding="utf-8", errors="replace")
q = queue.Queue()
def reader():
    for line in p.stdout:
        q.put((time.time(), line.rstrip()))
    q.put((time.time(), "EOF"))
threading.Thread(target=reader, daemon=True).start()

def send(payload):
    p.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n"); p.stdin.flush()

def recv(timeout, label=""):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            ts, line = q.get(timeout=1)
            if line == "EOF":
                print(f"  [{label}] EOF"); return None
            try:
                obj = json.loads(line)
            except Exception:
                print(f"  [{label}] non-json: {line[:120]}"); continue
            print(f"  [{label}] {time.time()-t0:.1f}s <- id={obj.get('id')} {'result' if 'result' in obj else obj.get('error')}")
            return obj
        except queue.Empty:
            pass
    print(f"  [{label}] TIMEOUT {timeout}s")
    return None

print("1) initialize")
send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}})
recv(20, "init")
send({"jsonrpc":"2.0","method":"notifications/initialized","params":{}})

print("2) tools/list")
send({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
r = recv(20, "tools")
if r: print("   tools:", [t["name"] for t in r["result"]["tools"]])

print("3) aec_preview")
send({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"aec_preview","arguments":{"instruction":"生成一个6m×4m的房间"}}})
recv(30, "preview")

print("4) aec_run simulation")
send({"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"aec_run","arguments":{"instruction":"生成一个6m×4m的房间","backend":"simulation","max_attempts":1,"output_root":"runs-probe"}}})
recv(120, "run")

print("5) closing stdin, waiting process exit")
try:
    p.stdin.close()
except Exception: pass
try:
    p.wait(timeout=15)
    print("  process exited:", p.returncode)
except subprocess.TimeoutExpired:
    print("  PROCESS WON'T EXIT — 退出卡死确认")
    p.kill()
