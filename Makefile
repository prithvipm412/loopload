.PHONY: setup backend frontend dev test

setup:
	python3.12 -m venv backend/.venv
	backend/.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

backend:
	cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) -j2 backend frontend

test:
	cd backend && PYTHONPATH=. .venv/bin/pytest -q
