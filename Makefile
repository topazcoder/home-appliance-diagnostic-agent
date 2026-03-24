run-server:
	@uv run uvicorn app.api.httpserver:app --host 0.0.0.0

seed:
	@uv run python -m scripts.seed