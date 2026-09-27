"""Run the real-evidence rhetoric benchmark with hardened writer and blind judge."""
from __future__ import annotations

import real_rhetoric_benchmark as benchmark
from robust_rhetoric_judge import judge
from robust_rhetoric_writer import response_text


if __name__ == "__main__":
    benchmark._judge = judge
    benchmark._response_text = response_text
    benchmark.main()
