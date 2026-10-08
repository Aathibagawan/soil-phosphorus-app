import io

import pytest

READING = {"soil_temperature": 17.5, "soil_humidity": 31, "electrical_conductivity": 54,
           "ph": 7.1, "air_temperature": 20, "air_humidity": 75, "light_intensity": 70000}


def H(cid):
    return {"X-Client-Id": cid}


def test_health_and_info(client):
    h = client.get("/api/health").json()
    assert h["model_loaded"] is True
    info = client.get("/api/model/info").json()
    assert info["window"] == 72 and len(info["features"]) == 7


def test_predict_single_reading(client, cid):
    r = client.post("/api/predict", json={"reading": READING, "label": "plot A"}, headers=H(cid))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["input_mode"] == "single_reading"
    assert len(d["attention"]) == d["window"] == 72
    assert abs(sum(d["attention"]) - 1) < 1e-3
    assert len(d["feature_effects"]) == 7
    assert any("Single reading" in w for w in d["warnings"])


def test_predict_window_matches_sample(client, cid):
    s = client.get("/api/model/sample").json()
    rows = [dict(zip(s["keys"], r)) for r in s["window"]]
    r = client.post("/api/predict", json={"window": rows}, headers=H(cid))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["input_mode"] == "time_series"
    # prediction should be in the neighbourhood of the true next value
    assert abs(d["prediction"] - s["actual_next"]) < 5


@pytest.mark.parametrize("field,value", [("ph", 14), ("soil_humidity", -3), ("air_temperature", 999),
                                         ("light_intensity", "abc"), ("ph", float("nan"))])
def test_validation_rejects_bad_values(client, field, value):
    bad = {**READING, field: value}
    import json
    r = client.post("/api/predict", content=json.dumps({"reading": bad}),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


def test_validation_missing_extra_and_exclusive(client):
    assert client.post("/api/predict", json={"reading": {"ph": 7}}).status_code == 422
    assert client.post("/api/predict", json={"reading": {**READING, "bogus": 1}}).status_code == 422
    assert client.post("/api/predict", json={}).status_code == 422
    assert client.post("/api/predict", json={"reading": READING, "window": [READING]}).status_code == 422


def test_short_window_rejected(client):
    r = client.post("/api/predict", json={"window": [READING] * 10})
    assert r.status_code == 422 and "72" in r.json()["detail"]


def test_out_of_range_warning(client):
    r = client.post("/api/predict", json={"reading": {**READING, "soil_temperature": 45}})
    assert any("outside the range" in w for w in r.json()["warnings"])


def test_history_lifecycle_and_isolation(client, cid):
    other = "other-" + cid
    for _ in range(3):
        client.post("/api/predict", json={"reading": READING}, headers=H(cid))
    client.post("/api/predict", json={"reading": READING}, headers=H(other))

    page = client.get("/api/history?limit=2", headers=H(cid)).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    first = page["items"][0]
    assert client.get(f"/api/history/{first['id']}", headers=H(cid)).status_code == 200
    assert client.get(f"/api/history/{first['id']}", headers=H(other)).status_code == 404   # isolation

    st = client.get("/api/history/stats", headers=H(cid)).json()
    assert st["count"] == 3 and len(st["series"]) == 3

    exp = client.get("/api/history/export.csv", headers=H(cid))
    assert exp.headers["content-type"].startswith("text/csv")
    assert len(exp.text.strip().splitlines()) == 4

    assert client.delete(f"/api/history/{first['id']}", headers=H(cid)).status_code == 204
    assert client.delete("/api/history", headers=H(cid)).status_code == 204
    assert client.get("/api/history", headers=H(cid)).json()["total"] == 0
    assert client.get("/api/history", headers=H(other)).json()["total"] == 1


def test_history_requires_client_id(client):
    assert client.get("/api/history").status_code == 400
    assert client.get("/api/history", headers={"X-Client-Id": "bad id!"}).status_code == 400


def _csv(n, header=None, bad_row=None):
    header = header or "Soil_Temperature,Soil_Humidity,Electrical_Conductivity,pH,Air_Temperature,Air_Humidity,Light_Intensity"
    lines = [header] + ["17.5,31,54,7.1,20,75,70000"] * n
    if bad_row:
        lines[3] = bad_row
    return "\n".join(lines).encode()


def test_csv_upload(client, cid):
    r = client.post("/api/predict/csv", files={"file": ("w.csv", io.BytesIO(_csv(80)), "text/csv")},
                    data={"label": "csv"}, headers=H(cid))
    assert r.status_code == 200, r.text
    assert r.json()["input_mode"] == "time_series"


def test_csv_errors(client):
    f = lambda b: {"file": ("w.csv", io.BytesIO(b), "text/csv")}
    r = client.post("/api/predict/csv", files=f(_csv(80, header="a,b,c")))
    assert r.status_code == 422 and r.json()["detail"]["details"]
    r = client.post("/api/predict/csv", files=f(_csv(80, bad_row="17,31,54,99,20,75,70000")))
    assert r.status_code == 422 and "line 4" in r.json()["detail"]["details"][0]
    assert client.post("/api/predict/csv", files=f(_csv(10))).status_code == 422


def test_docs_and_ui_served(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
