build:
	docker compose build

run:
	docker compose run --rm chess-engine

test: # haven't implemented yet
	docker compose run --rm chess-engine pytest

notebook: # debugging using notebook visualization
	docker compose run --rm \
		-p 8888:8888 \
		chess-engine \
		jupyter notebook \
		--ip=0.0.0.0 \
		--allow-root \
		--NotebookApp.token=''