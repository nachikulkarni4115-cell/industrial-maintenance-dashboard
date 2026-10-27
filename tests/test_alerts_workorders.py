def login(client, username="mgr_north", password="Manager123!"):
    client.post("/auth/login", data={"username": username, "password": password})


def test_list_alerts(client):
    login(client)
    r = client.get("/alerts/")
    assert r.status_code == 200
    assert b"Alert" in r.data


def test_list_workorders(client):
    login(client)
    r = client.get("/workorders/")
    assert r.status_code == 200


def test_viewer_cannot_create_workorder(client):
    login(client, "viewer_north", "Viewer123!")
    r = client.get("/workorders/new")
    assert r.status_code == 403
