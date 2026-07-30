.PHONY: test
test:
	uv run pytest --doctest-modules -W error
	uv run screenplain tests/files/simple.fountain /tmp/simple.pdf

.PHONY: lint
lint:
	uvx prek run -a