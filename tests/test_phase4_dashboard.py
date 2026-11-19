def test_dashboard_page_rendered(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    html = r.text
    assert "OrderMate AI" in html
    assert "Live Orders" in html
    assert "Bulk Upload Menu from CSV" in html
    assert "WhatsApp Simulator" in html or "wa-dark" in html
    assert "Meta WhatsApp Setup" in html


def test_home_returns_dashboard_link(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["message"] == "Welcome to OrderMate AI"
    assert data["dashboard_url"] == "/dashboard"
