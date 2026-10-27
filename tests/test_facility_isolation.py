def login(client, username, password="Manager123!"):
    return client.post("/auth/login", data={"username": username, "password": password}, follow_redirects=True)


def test_north_manager_sees_only_north_equipment(client):
    login(client, "mgr_north")
    r = client.get("/equipment/")
    assert r.status_code == 200
    assert b"MTR-001" in r.data
    assert b"MTR-S01" not in r.data  # south asset must be invisible


def test_south_manager_cannot_see_north_equipment(client):
    login(client, "mgr_south")
    r = client.get("/equipment/")
    assert r.status_code == 200
    assert b"MTR-S01" in r.data
    assert b"MTR-001" not in r.data


def test_north_manager_cannot_access_south_detail(client, app):
    from app.models import Equipment
    with app.app_context():
        south = Equipment.query.filter_by(asset_tag="MTR-S01").first()
        assert south is not None
        eq_id = south.id
    login(client, "mgr_north")
    r = client.get(f"/equipment/{eq_id}")
    assert r.status_code == 403


def test_viewer_cannot_create_equipment(client):
    login(client, "viewer_north", "Viewer123!")
    r = client.get("/equipment/new")
    assert r.status_code == 403
