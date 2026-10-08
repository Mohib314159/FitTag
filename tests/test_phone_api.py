"""Phone capture behavior, limits and real engine integration on synthetic inputs."""
import io
import json
import threading
from pathlib import Path
import cv2
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from api import server

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client():
    with TestClient(server.app) as test_client:
        yield test_client


def photo(button=True, crop=False):
    img = np.full((1200, 900, 3), 235, np.uint8)
    pts = np.array([[250,80],[650,80],[710,230],[690,1120],[510,1120],
                    [450,420],[390,1120],[210,1120],[190,230]], np.int32)
    cv2.fillPoly(img, [pts], (68,54,35))
    if button:
        cv2.circle(img, (450,104), 10, (200,200,200), -1)
    if crop:
        img = img[80:]
    return cv2.imencode(".jpg", img)[1].tobytes()


def upload(client, raw=None, **data):
    return client.post("/measure", files={"file": ("jeans.jpg", raw or photo(), "image/jpeg")}, data=data)


def test_hardware_route_and_overlay(client):
    response = upload(client, diameter_mm=20, known_diameter="true")
    assert response.status_code == 200
    result = response.json()
    assert result["ok"] and result["reference"] == "hardware"
    assert result["confidence"] == "estimate"
    rows = {m["name"]: m for m in result["garment"]["measurements"]}
    assert 35 < rows["waist_flat"]["value_cm"] < 50
    for m in rows.values():
        assert m["tolerance_cm"] >= round(m["value_cm"] * .10, 1)
        assert len(m["p1"]) == len(m["p2"]) == 2
    overlay = client.get(result["overlay_url"])
    assert overlay.status_code == 200
    assert overlay.headers["content-type"] == "image/png"
    assert overlay.headers["cache-control"] == "no-store"
    assert response.headers["cache-control"] == "no-store"


def test_photoreal_hardware_waist_is_not_a_narrow_top_fragment(client):
    result = upload(client, (ROOT / "web/example-photo.jpg").read_bytes()).json()
    assert result["ok"], result
    rows = {m["name"]: m for m in result["garment"]["measurements"]}
    assert .60 <= rows["waist_flat"]["value_cm"] / rows["hip_flat"]["value_cm"] <= 1.25
    assert rows["waist_flat"]["value_cm"] > 20


@pytest.mark.parametrize("raw,message", [(photo(False),"button"),(photo(crop=True),"edge")], ids=["no-button", "cropped"])
def test_refusals_preserve_honesty(client, raw, message):
    result = upload(client, raw).json()
    assert result["ok"] is False
    assert message in result["error"].lower()
    assert "garment" not in result


def test_overly_tilted_button_refused(client, monkeypatch):
    import core.phone as phone
    monkeypatch.setattr(phone, "find_button", lambda *a, **k: ((450.,104.), (12.,20.), 0.))
    monkeypatch.setattr(phone, "refine_disc", lambda img, ellipse: ellipse)
    result = upload(client).json()
    assert not result["ok"] and "tilted" in result["error"]


def test_invalid_modes_and_uploads(client):
    assert upload(client, b"broken image").status_code == 400
    assert upload(client, reference="invented").status_code == 422
    assert upload(client, diameter_mm="NaN").status_code == 422
    assert upload(client, diameter_mm="9").status_code == 422
    result = upload(client, garment_type="t-shirt").json()
    assert not result["ok"] and "paper" in result["error"]
    assert upload(client, b"x" * (12 * 1024 * 1024 + 1)).status_code == 413


def test_exif_orientation_and_resize(client, monkeypatch):
    observed = []
    monkeypatch.setattr(server, "_phone_measure", lambda img, *args: observed.append(img.shape) or {"ok": False})
    img = Image.new("RGB", (2400,1200), "white")
    exif=Image.Exif();exif[274]=6
    raw=io.BytesIO();img.save(raw,"JPEG",exif=exif)
    upload(client,raw.getvalue())
    assert observed == [(1800,900,3)]


def test_busy_service_still_answers_health(client, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def busy(*args):
        entered.set(); release.wait(5)
        return {"ok": False, "error": "test"}
    monkeypatch.setattr(server,"_phone_measure",busy)
    thread = threading.Thread(target=lambda: upload(client)); thread.start()
    try:
        assert entered.wait(3)
        assert client.get("/health").status_code == 200
        response=upload(client)
        assert response.status_code == 429 and response.headers["retry-after"] == "5"
    finally:
        release.set();thread.join(5)


def test_installable_assets_and_private_dataset(client):
    for path in ("/", "/app.js", "/app.css", "/client.mjs", "/sw.js", "/demo.json", "/demo.jpg"):
        assert client.get(path).status_code == 200, path
    manifest=client.get("/manifest.webmanifest").json()
    assert manifest["display"] == "standalone"
    for icon in manifest["icons"]:
        assert client.get('/'+icon["src"].removeprefix('./')).status_code == 200
    assert client.get('/sw.js').headers['cache-control']=='no-cache'
    samples=json.loads((ROOT/'docs/data/samples.json').read_text(encoding='utf-8'))
    assert all(not s['id'].startswith('jeans-carhartt') for s in samples)
    real=json.loads((ROOT/'docs/data/real.json').read_text(encoding='utf-8'))
    assert 'cm' not in real and 'absolute_photo_differences_cm' in real


def test_legacy_reference_route_uses_phone_engine(client):
    response=client.post('/measure-reference',files={'file':('jeans.jpg',photo(),'image/jpeg')})
    assert response.json()['reference']=='hardware'


def test_missing_paper_is_explicit_failure(client):
    result=upload(client, reference='a4').json()
    assert result['ok'] is False and 'rectangle' in result['error']


def test_marker_fallback_still_runs_through_phone_api(client):
    from tests.synth import make_jeans_photo
    img, _ = make_jeans_photo()
    raw=cv2.imencode('.png',img)[1].tobytes()
    result=upload(client,raw,reference='mat').json()
    assert result['ok'], result
    assert result['reference']=='mat' and result['confidence']=='check-overlay'
    assert len(result['garment']['measurements'])>=5
