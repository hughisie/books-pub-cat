import io, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import capi_relay as c

class H:
    def __init__(self, body, origin="https://books.pub.cat", ip="1.2.3.4"):
        self.headers = {"Origin": origin, "CF-Connecting-IP": ip, "User-Agent": "UA"}
        self.client_address = ("172.18.0.2", 1)
        self._capi_raw = json.dumps(body).encode()
        self.sent = None
    def _send(self, code, obj, hdrs=None):
        self.sent = (code, hdrs)

class R:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False

def ok_body(**kw):
    b = {"event_name": "ViewContent", "event_id": "vc-1", "event_source_url": "https://books.pub.cat/shams-al-maarif/",
         "custom_data": {"content_ids": ["shams-al-maarif"], "email": "x@y.z"}, "fbp": "fb.1.1.2", "fbc": "bad"}
    b.update(kw); return b

ENV = {"BOOKS_META_PIXEL_ID": "123", "BOOKS_META_CAPI_TOKEN": "tok"}

def run(h, env=ENV):
    calls = []
    def opener(req, timeout):
        calls.append(req); return R()
    c.handle(h, env=env, opener=opener, background=False)
    return calls

def test_forwards_clean_event():
    calls = run(H(ok_body()))
    assert len(calls) == 1
    sent = json.loads(calls[0].data)["data"][0]
    assert sent["event_id"] == "vc-1" and sent["user_data"]["client_ip_address"] == "1.2.3.4"
    assert "email" not in json.dumps(sent) and "fbc" not in sent["user_data"] and sent["user_data"]["fbp"] == "fb.1.1.2"
    assert "/123/events" in calls[0].full_url

def test_inert_without_config():
    h = H(ok_body()); assert run(h, env={}) == [] and h.sent[0] == 204

def test_rejects_other_origin_event_and_url():
    assert run(H(ok_body(), origin="https://evil.example")) == []
    assert run(H(ok_body(event_name="Purchase"), ip="5.5.5.5")) == []
    assert run(H(ok_body(event_source_url="https://evil.example/"), ip="6.6.6.6")) == []

def test_rate_limit():
    n = 0
    for i in range(70):
        n += len(run(H(ok_body(event_id=f"e{i}"), ip="9.9.9.9")))
    assert n == c.MAX_PER_MIN

def test_value_cleaning():
    ev = c.build_event({"event_name": "AddToCart", "event_id": "a", "event_source_url": "https://books.pub.cat/x/",
                        "custom_data": {"value": "12.99", "currency": "USD", "content_ids": ["B0H12C7HNN"]}}, "1.1.1.1", "UA")
    assert ev["custom_data"] == {"value": 12.99, "currency": "USD", "content_ids": ["B0H12C7HNN"]}

if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"): f(); print("pass", k)
