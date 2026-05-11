"""Audit workpaper benchmark suite.

This package contains everything needed to:
1. Generate simulated client deliverables with planted audit errors
   (under benchmarks.generators, benchmarks.materials, benchmarks.ground_truth)
2. Run an Agent that reads only client deliverables and fills a standard
   audit workpaper (under benchmarks.agent, benchmarks.template_builder)
3. Compare Agent output to ground truth and compute Precision/Recall/F1
   (under benchmarks.evaluator)

Strict isolation rule
---------------------
Code under ``benchmarks.agent`` MUST NOT import anything from
``benchmarks.ground_truth``. The Agent is supposed to operate blindly
on the materials and never see the "answer key". A pre-commit check
enforces this.
"""
