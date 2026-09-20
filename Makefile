# FidusAchates. Rust is not required on the host: every target runs in a
# container, so `make docker-test` needs only Docker (and Docker is optional if
# Rust and Python are installed locally).

IMAGE ?= rust:1-slim
CARGO ?= cargo
DOCKER_RUN = docker run --rm --user "$$(id -u):$$(id -g)" \
	-e CARGO_HOME=/w/.cache/cargo -v "$$(pwd)":/w:z -w /w

.PHONY: test test-trace build release clippy fmt lab docker-test docker-test-offline clean

test:
	$(CARGO) test --workspace

test-trace:
	$(CARGO) test --workspace --features research-trace

release:
	$(CARGO) build --release

clippy:
	$(CARGO) clippy --workspace --all-targets -- -D warnings

fmt:
	$(CARGO) fmt --all -- --check

lab:
	cd lab && python3 -m pytest

# In-container equivalents. `fetch` needs the network once; everything else runs
# with --network=none to prove the build is self-contained (NFR-10).
docker-fetch:
	$(DOCKER_RUN) $(IMAGE) cargo fetch

docker-test: docker-fetch docker-test-offline

docker-test-offline:
	$(DOCKER_RUN) --network=none $(IMAGE) \
		cargo test --workspace --offline --target-dir /w/.cache/target
	$(DOCKER_RUN) --network=none $(IMAGE) \
		cargo test --workspace --offline --features research-trace --target-dir /w/.cache/target

clean:
	rm -rf .cache/target target
