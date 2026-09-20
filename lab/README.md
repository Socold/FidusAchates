# fidus-lab

The offline half of FidusAchates (ADR-0010). It never runs continuously and
never touches `/dev/input`. It reads reduced traces written by the recorder,
replays them, and will host the signal study and the evaluation bench.

Python 3.12+, standard library only for the trace reader.

    cd lab && python3 -m pytest

The reader is tested against the same fixtures as the Rust writer, so the two
languages cannot drift on the trace format (roadmap 1.7 / 2.x).
