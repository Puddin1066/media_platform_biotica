"""Run the real-evidence rhetoric benchmark with the hardened blind judge."""
from __future__ import annotations

import real_rhetoric_benchmark as benchmark
from robust_rhetoric_judge import judge


if __name__ == "__main__":
    benchmark._judge = judge
    benchmark.main()
