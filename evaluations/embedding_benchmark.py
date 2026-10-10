"""Compare local CPU embedding settings; no PDF data or LLM calls.

Run with python -m evaluations.embedding_benchmark. Downloads MiniLM if absent.
Results are machine-specific, not Streamlit Cloud performance measurements.
"""
import json
import os
import time
from functools import cached_property

import numpy as np
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

class BoundedMiniLM(ONNXMiniLM_L6_V2):
    """Experimental setting only; not used by the application."""

    @cached_property
    def model(self):
        options = self.ort.SessionOptions()
        options.log_severity_level = 3
        options.graph_optimization_level = self.ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        return self.ort.InferenceSession(
            os.path.join(self.DOWNLOAD_PATH, self.EXTRACTED_FOLDER_NAME, "model.onnx"),
            providers=["CPUExecutionProvider"], sess_options=options,
        )


def main():
    documents = [
        ("Operating systems manage processes, memory, scheduling and files. " * 14),
        ("Computer networks transmit packets using routing and transport protocols. " * 14),
    ] * 16
    results = {}
    vectors = []
    for label, model in (
        ("default", ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])),
        ("bounded", BoundedMiniLM(preferred_providers=["CPUExecutionProvider"])),
    ):
        started = time.perf_counter()
        model(documents[:1])
        cold_seconds = time.perf_counter() - started
        samples = []
        for _ in range(3):
            started = time.perf_counter()
            output = model(documents)
            samples.append(round(time.perf_counter() - started, 3))
        vectors.append(np.asarray(output))
        results[label] = {"initialization_seconds": round(cold_seconds, 3), "batch_32_seconds": samples}
    results["max_vector_difference"] = float(np.max(np.abs(vectors[0] - vectors[1])))
    np.testing.assert_allclose(vectors[0], vectors[1], atol=1e-5, rtol=1e-4)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
