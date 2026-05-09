build:
	docker compose build

run:
	docker compose run --rm chess-engine

test:
	docker compose run --rm chess-engine pytest tests/