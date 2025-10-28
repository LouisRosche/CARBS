.PHONY: setup start stop logs test clean

setup:
	python -m venv venv
	./venv/bin/pip install -r requirements.txt
	cp .env.example .env
	@echo "✅ Setup complete. Edit .env with your settings"

start:
	docker compose up -d
	@echo "✅ Infrastructure started"

stop:
	docker compose down

logs:
	docker compose logs -f

db-init:
	python scripts/init_db.py

run:
	python src/main.py

test:
	pytest tests/ -v --cov=src

format:
	black src/ tests/
	isort src/ tests/

lint:
	flake8 src/ tests/
	mypy src/

clean:
	docker compose down -v
	rm -rf venv __pycache__ .pytest_cache
