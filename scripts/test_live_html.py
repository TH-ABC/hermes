import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
r = urllib.request.urlopen('https://hermes-agent-vercel.vercel.app/')
html = r.read().decode('utf-8')
print("Has loadLivePoolAccounts:", "loadLivePoolAccounts" in html)
print("Has removeItem:", "localStorage.removeItem('hermes_pool_accounts')" in html)

for match in re.finditer(r'"name":\s*"(\w+)"', html):
    start = match.start()
    block = html[start:start+500]
    m_lbl = re.search(r'"reset_label":\s*"([^"]+)"', block)
    m_v = re.search(r'"video_state":\s*"([^"]+)"', block)
    if m_lbl:
        print(match.group(1), "->", m_lbl.group(1), "| video:", m_v.group(1) if m_v else "none")
