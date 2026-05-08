build:
	docker compose build

run:
	docker compose run --rm chess-engine

test: # haven't implemented yet
	docker compose run --rm chess-engine pytest

notebook: # debugging using notebook visualization
	docker compose up -d analysis