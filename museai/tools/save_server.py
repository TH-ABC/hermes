"""Local save relay: Muse tab postMessages a file buffer to this page, which POSTs it here to be written to disk."""
import os, re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        html = b"""<!doctype html><meta charset=utf-8><title>save relay</title><pre id=o>ready</pre><script>
addEventListener('message',async e=>{if(!e.data||!e.data.buf)return;const o=document.getElementById('o');o.textContent='saving '+e.data.buf.byteLength;
const t=await (await fetch('/?name='+encodeURIComponent(e.data.name),{method:'POST',body:e.data.buf})).text();o.textContent=t;
(e.source||opener).postMessage({saved:t},'*');});
if(opener) opener.postMessage({relay:'ready'},'*');
</script>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html)

    def do_POST(self):
        name = parse_qs(urlparse(self.path).query).get("name", ["upload.bin"])[0]
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename(name))
        n = int(self.headers.get("Content-Length", 0))
        path = os.path.join(HERE, name)
        with open(path, "wb") as f:
            f.write(self.rfile.read(n))
        body = f"saved {path} {n}".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("127.0.0.1", 8798), H).serve_forever()
