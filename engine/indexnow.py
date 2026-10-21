"""IndexNow ping (Bing, Yandex, Seznam...; Bing also feeds Copilot and ChatGPT search).
Setup per client: put a file named <key>.txt containing <key> at the site root, and set [indexnow] key in client.toml."""
import requests

from common import log

L = log("indexnow")


def submit(cfg, urls):
    key = cfg.get("indexnow", {}).get("key")
    if not key or not urls:
        return
    host = cfg["domain"]
    r = requests.post("https://api.indexnow.org/indexnow", timeout=30,
                      json={"host": host, "key": key, "keyLocation": f"https://{host}/{key}.txt", "urlList": list(urls)})
    L.info("%s: IndexNow %s for %d urls", cfg["slug"], r.status_code, len(urls))
