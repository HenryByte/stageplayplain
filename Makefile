.PHONY: test
test:
	uv run pytest --doctest-modules -W error -m "not perf"
	uv run screenplain tests/files/simple.fountain /tmp/simple.pdf

# Benchmark the Fountain parser against examples/Big-Fish.fountain.
# Pass ARGS to save/compare runs, e.g.
#   make perf ARGS=--benchmark-autosave
#   make perf ARGS='--benchmark-compare --benchmark-compare-fail=mean:10%'
.PHONY: perf
perf:
	uv run pytest tests/perf -m perf --benchmark-columns=min,mean,stddev,rounds $(ARGS)

.PHONY: lint
lint:
	uvx prek run -a