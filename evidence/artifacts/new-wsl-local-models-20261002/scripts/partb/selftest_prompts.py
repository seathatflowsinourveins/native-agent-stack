#!/usr/bin/env python3
"""Observation requested by the review of the Part B scripts: build E1 and E2 exactly as partb_arms.build does, replace
the wrapper's request for embeddings with a stub that records the texts it would send and returns zeros, and encode two
queries and two documents of the frozen task through MTEB's own dataloader. Prints the first two strings of each kind
per arm, so the prompts that reach the server are observed, not inferred. Loads no model; the server only answers its
model list."""
import numpy as np
from mteb._create_dataloaders import create_dataloader
from mteb.models import OpenAIAPIEncodeWrapper
from mteb.types import PromptType

import partb_arms

sent = []


def stub(self, texts):
    sent.extend(texts)
    return np.zeros((len(texts), 8), dtype=np.float32)


OpenAIAPIEncodeWrapper._get_embeddings = stub
the_task = partb_arms.task()
the_task.load_data()
split = the_task.dataset["default"]["test"]
queries, documents = split["queries"].select(range(2)), split["corpus"].select(range(2))
for arm in ("E1", "E2"):
    model = partb_arms.build(arm)
    for kind, data in (("query", queries), ("document", documents)):
        sent.clear()
        prompt_type = PromptType.query if kind == "query" else PromptType.document
        loader = create_dataloader(data, task_metadata=the_task.metadata, prompt_type=prompt_type, batch_size=2)
        model.encode(loader, task_metadata=the_task.metadata, hf_split="test", hf_subset="default",
                     prompt_type=prompt_type, show_progress_bar=False)
        for text in sent[:2]:
            print(arm, kind, repr(text[:110]))
