def test_login_page(client):
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert b"Sign In" in r.data


def test_login_success(client):
    r = client.post("/auth/login", data={
        "username": "admin",
        "password": "testadminpass",  # TestingConfig password
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"Overview" in r.data or b"Operations" in r.data


def test_login_invalid(client):
    r = client.post("/auth/login", data={
        "username": "admin",
        "password": "wrongpassword",
    }, follow_redirects=True)
    assert b"Invalid username or password" in r.data


def test_logout(client):
    client.post("/auth/login", data={"username": "admin", "password": "testadminpass"})
    r = client.get("/auth/logout", follow_redirects=True)
    assert b"Sign In" in r.data or b"signed out" in r.data.lower()
