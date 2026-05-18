# TTNBP-Chess

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

## Build Environment 

```bash
make build
```
> NOTE: Use when modify requirements.txt

## Run the Engine

```bash
make run
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

Hiện tại, sẽ dùng jupyter để xem bước đi, xong cuối cùng sẽ hướng về UCI để chỗ khác render thay mình.
```
