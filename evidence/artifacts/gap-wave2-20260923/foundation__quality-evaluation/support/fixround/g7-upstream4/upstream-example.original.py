import numpy as np
import requests

MODEL = "nvidia/Nemotron-3-Embed-1B-BF16"
URL = "http://localhost:8000/v2/embed"

QUERIES = [
    "Write a Python function that counts the frequency of each element in a list of lists.",
    "Write a function that orders a dictionary with tuple keys by the product of each key's tuple values.",
    "What symptoms and common triggers help distinguish eczema from other inflammatory skin conditions?",
    "How can someone reduce exposure to pollen during allergy season?",
]

DOCUMENTS = [
    "def frequency_lists(list1):\n    flattened = [item for sublist in list1 for item in sublist]\n    counts = {}\n    for item in flattened:\n        if item in counts:\n            counts[item] += 1\n        else:\n            counts[item] = 1\n    return counts",
    "def sort_dict_item(test_dict):\n    return {key: test_dict[key] for key in sorted(test_dict.keys(), key=lambda ele: ele[0] * ele[1])}",
    "Eczema commonly causes itchy, dry, inflamed patches of skin. The affected areas may look red, scaly, cracked, or darker than the surrounding skin depending on skin tone. Symptoms can flare after exposure to irritants, allergens, stress, or changes in weather.",
    "People with pollen allergy can reduce exposure by staying indoors on dry, windy days, avoiding early-morning outdoor activity, and going outside after rain when pollen levels are lower. They should check pollen forecasts, close windows and doors when counts are high, and consider starting allergy medication before symptoms begin if high pollen is expected. After being outside, showering, changing clothes, avoiding outdoor laundry drying, and wearing a face mask for yard work can help limit pollen contact.",
]

def embed(input_type: str, texts: list[str]) -> np.ndarray:
    response = requests.post(
        URL,
        json={
            "model": MODEL,
            "input_type": input_type,
            "texts": texts,
            "embedding_types": ["float"],
            "truncate": "END",
        },
        timeout=120,
    )
    response.raise_for_status()
    return np.array(response.json()["embeddings"]["float"], dtype=np.float32)

query_embeddings = embed("query", QUERIES)
document_embeddings = embed("document", DOCUMENTS)

scores = query_embeddings @ document_embeddings.T
print("Similarity scores:")
print(f"{'':>4}" + "".join(f"d[{i}]".rjust(10) for i in range(scores.shape[1])))
for query_index, row in enumerate(scores):
    print(f"q[{query_index}]" + "".join(f"{score:>10.4f}" for score in row))
