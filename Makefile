.PHONY: help up down logs test ingest eval load scan-secrets clean-clone-test

help:
	@echo "PV-Triage Service Commands"
	@echo "  make up               - Start all Docker Compose services"
	@echo "  make down             - Stop all Docker Compose services"
	@echo "  make logs             - Tail service logs"
	@echo "  make test             - Run test suite"
	@echo "  make ingest           - Run corpus ingestion pipeline"
	@echo "  make eval             - Run evaluation suite"
	@echo "  make load             - Run Locust load test"
	@echo "  make scan-secrets     - Scan working tree and git history for secrets"
	@echo "  make clean-clone-test - Run end-to-end verification from fresh clone"

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	python3.11 -m pytest api/tests/ -v

ingest:
	@echo "not implemented yet"

eval:
	@echo "not implemented yet"

load:
	@echo "not implemented yet"

scan-secrets:
	@bash ./scripts/scan_secrets.sh

clean-clone-test:
	@echo "not implemented yet"
