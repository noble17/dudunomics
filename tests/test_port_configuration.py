from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_backend_default_ports_are_3333_and_8888():
    frontend_package = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    next_config = (ROOT / "frontend" / "next.config.ts").read_text(encoding="utf-8")
    backend_dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "next dev --turbopack -p 3333" in frontend_package
    assert "http://localhost:8888" in next_config
    assert "EXPOSE 8888" in backend_dockerfile
    assert '"--port", "8888"' in backend_dockerfile
    assert '"8888:8888"' in compose
    assert '"3333:3333"' in compose
    assert "http://localhost:8888/health" in compose
    assert "API_URL=http://api:8888" in compose
