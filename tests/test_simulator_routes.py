def test_simulator_trigger_requires_login(client):
    response = client.post("/dashboard/simulator/run")
    assert response.status_code in (302, 401)


def test_simulator_trigger_requires_server_image_configuration(client, app):
    response = client.post("/auth/login", data={
        "username": "admin",
        "password": "testadminpass",
    })
    assert response.status_code in (302, 200)

    app.config["SIMULATOR_JOB_IMAGE"] = ""
    response = client.post("/dashboard/simulator/run")
    assert response.status_code == 503
    assert b"Simulator image is not configured" in response.data
