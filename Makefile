install-backend:
	python -m pip install -r backend/requirements.txt

install-frontend:
	cd frontend && npm install

run-backend:
	cd backend && uvicorn app.main:app --reload

run-frontend:
	cd frontend && npm run dev

up:
	docker compose up --build
