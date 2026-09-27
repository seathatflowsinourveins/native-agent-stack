"""Run the official LongMemEval runner unchanged for the oracle retriever on a CUDA-less Mac.

The runner sizes its process pool from torch.cuda.device_count(), which is 0 here, although the
oracle path loads no model. This shim reports one device and then executes run_retrieval.py as-is.
"""
import runpy
import sys

import torch

torch.cuda.device_count = lambda: 1
sys.argv = ["run_retrieval.py"] + sys.argv[1:]
runpy.run_path("run_retrieval.py", run_name="__main__")
