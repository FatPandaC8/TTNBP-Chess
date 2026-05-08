# TTNBP-Chess
````markdown
# TTNBP Chess Engine

A modular Python chess engine focused on clean architecture and extensibility.

---

# Project Structure

```txt
src/engine
├── board/          # Board representation and move generation
├── evaluation/     # Position evaluation
├── protocols/      # UCI / external protocols
├── search/
│   ├── heuristics/ # Search heuristics
│   ├── ordering/   # Move ordering
│   └── pruning/    # Pruning techniques
├── utils/          # Shared utilities
├── base.py
└── __init__.py
````

---

# Running the Project

## Build Docker Environment (Haven't write the file yet hehe)

```bash
docker compose build
```

## Run the Engine

```bash
docker compose run --rm chess-engine
```

## Run Tests

```bash
docker compose run --rm chess-engine pytest
```

---

# Adding New Features

## Search Pruning

Add pruning techniques inside:

```txt
src/engine/search/pruning/
```
---

## Move Ordering

Add move ordering techniques inside:

```txt
src/engine/search/ordering/
```
---

## Search Heuristics

Add general search heuristics inside:

```txt
src/engine/search/heuristics/
```

---

## Evaluation Logic

Add evaluation components inside:

```txt
src/engine/evaluation/
```
---

## Board Logic

Add board-related features inside:

```txt
src/engine/board/
```
---

# Guidelines

Put config variables in the config folder with the format:
config/module_name/config.yml
```
```
