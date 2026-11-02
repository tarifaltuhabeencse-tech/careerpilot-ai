import os, tempfile
tmp=tempfile.mkdtemp(prefix="careerpilot-test-")
os.environ["CAREERPILOT_DATABASE_URL"]="sqlite:///"+tmp+"/test.db"
os.environ["CAREERPILOT_SECRET_KEY"]="testing-only-secret"
from fastapi.testclient import TestClient
from backend.app.main import app, build_match
client=TestClient(app)
def register(email="user@example.com"):
    r=client.post("/api/auth/register",json={"email":email,"password":"strong-password-123"})
    assert r.status_code==201,r.text
    return r.json()["access_token"]
def test_health(): assert client.get("/health").json()["status"]=="ok"
def test_auth_and_protected_route():
    token=register()
    assert client.get("/api/me").status_code==401
    assert client.get("/api/me",headers={"Authorization":"Bearer "+token}).status_code==200
    assert client.post("/api/auth/login",json={"email":"user@example.com","password":"wrong-password"}).status_code==401
def test_duplicate_user():
    register("dup@example.com")
    assert client.post("/api/auth/register",json={"email":"dup@example.com","password":"strong-password-123"}).status_code==409
def test_match_components():
    result=build_match("Python SQL bachelor degree project experience","Required Python and SQL. Preferred Power BI.")
    assert 0<=result["score"]<=100
    assert "Python" in result["required_skills_found"]
    assert "Power BI" in result["preferred_skills_missing"]
    assert "components" in result
def test_unsupported_file():
    token=register("file@example.com")
    r=client.post("/api/analyze",headers={"Authorization":"Bearer "+token},data={"job_description":"Python developer"},files={"cv_file":("cv.txt",b"Python skills","text/plain")})
    assert r.status_code==415
def test_missing_analysis_not_disclosed():
    token=register("owner@example.com")
    assert client.get("/api/analyses/999999",headers={"Authorization":"Bearer "+token}).status_code==404
