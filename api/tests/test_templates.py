from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_templates_returns_defaults():
  response = client.get("/v1/templates")
  assert response.status_code == 200
  payload = response.json()
  assert isinstance(payload, list)
  assert payload
  first = payload[0]
  assert "id" in first
  assert "title" in first
  assert "genre" in first
  assert "content_rating" in first


def test_get_template_returns_definition():
  list_response = client.get("/v1/templates")
  template_id = list_response.json()[0]["id"]
  response = client.get(f"/v1/templates/{template_id}")
  assert response.status_code == 200
  payload = response.json()
  assert payload["id"] == template_id
  assert payload["story"]
  assert payload["slots"]


def test_get_template_unknown_returns_404():
  response = client.get("/v1/templates/t-not-real")
  assert response.status_code == 404
