#!/usr/bin/env python3
"""Install the Pub.Cat Books Meta pixel (dataset) id and its Conversions API token on London.
Portal card books-meta-pixel-paste (12 Oct 2026, cc-metaturn1). The portal worker pipes what Owen
pasted on stdin: either "<dataset id>|<token>" or the token alone (then the dataset is found from the
token's own permissions). Checks the token can read that dataset, backs up the secrets file, then
writes BOOKS_META_PIXEL_ID and BOOKS_META_CAPI_TOKEN. Never prints the token. Sends no event to Meta.
"""
import json, os, re, shutil, sys, time, urllib.error, urllib.request

ENV = os.environ.get("BOOKS_SECRETS_ENV", "/opt/pubcat/secrets/.env")
GRAPH = "https://graph.facebook.com/v21.0"


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b"{}")
        except ValueError:
            return {"error": {"message": f"HTTP {e.code}"}}


def is_pixel(pid, token):
    d = get(f"{GRAPH}/{pid}?fields=id,name&access_token={token}")
    return d if d.get("id") == pid else None


def main():
    raw = sys.stdin.read().strip()
    pid, token = (raw.split("|", 1) + [""])[:2] if "|" in raw else ("", raw)
    pid, token = pid.strip(), token.strip()
    if pid and not re.fullmatch(r"\d{10,20}", pid):
        sys.exit("STOP: the part before the | is not a dataset ID (it should be 15 or 16 digits).")
    if len(token) < 40:
        sys.exit("STOP: the token is too short. Copy the whole token from Events Manager.")
    if not pid:
        dbg = get(f"{GRAPH}/debug_token?input_token={token}&access_token={token}").get("data", {})
        ids = {t for g in dbg.get("granular_scopes", []) for t in g.get("target_ids", [])}
        found = [i for i in sorted(ids) if is_pixel(i, token)]
        if len(found) != 1:
            sys.exit("STOP: could not tell which dataset this token is for. Paste it again as: dataset ID, then |, then the token.")
        pid = found[0]
    px = is_pixel(pid, token)
    if not px:
        sys.exit("STOP: Meta says this token cannot read that dataset. Check you generated it on the Pub.Cat Books dataset.")
    print(f"token can read dataset {pid} ({px.get('name', 'no name')})")
    text = open(ENV).read()
    shutil.copy2(ENV, f"{ENV}.bak-books-meta-{time.strftime('%Y%m%d-%H%M%S')}")
    for k, v in (("BOOKS_META_PIXEL_ID", pid), ("BOOKS_META_CAPI_TOKEN", token)):
        line = f"{k}={v}"
        text = re.sub(rf"^{k}=.*$", line, text, flags=re.M) if re.search(rf"^{k}=", text, re.M) else text.rstrip("\n") + "\n" + line + "\n"
    tmp = ENV + ".tmp-books-meta"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.chmod(tmp, os.stat(ENV).st_mode & 0o777)
    os.replace(tmp, ENV)
    print("saved BOOKS_META_PIXEL_ID and BOOKS_META_CAPI_TOKEN on London (backup kept)")


if __name__ == "__main__":
    main()
