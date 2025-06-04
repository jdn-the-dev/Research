#!/usr/bin/env python3
import requests
import os
import json
from pathlib import Path

def read_fasta(fasta_path):
    """Read a FASTA file and return the sequence."""
    with open(fasta_path) as f:
        lines = f.readlines()
        sequence = ''
        for line in lines:
            if not line.startswith('>'):
                sequence += line.strip()
    return sequence

# Get the FASTA file path
fasta_path = input("Enter path to FASTA file: ")
sequence = read_fasta(fasta_path)

# Calculate appropriate number of tokens (roughly 1/3 of sequence length as a starting point)
# Adjust token count to avoid timeout (using a smaller fraction)
num_tokens = min(2000, len(sequence) // 4)  # Cap at 2000 tokens

key = os.getenv("NVCF_RUN_KEY") or "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"

r = requests.post(
    url=os.getenv("URL", "https://health.api.nvidia.com/v1/biology/arc/evo2-40b/generate"),
    headers={"Authorization": f"Bearer {key}"},
    json={
        "sequence": sequence,
        "num_tokens": num_tokens,
        "top_k": 1,
        "enable_sampled_probs": True,
    },
)

if "application/json" in r.headers.get("Content-Type", ""):
    print(r, "Saving to output.json:\n", r.text[:200], "...")
    Path("output.json").write_text(r.text)
elif "application/zip" in r.headers.get("Content-Type", ""):
    print(r, "Saving large response to data.zip")
    Path("data.zip").write_bytes(r.content)
else:
    print(r, r.headers, r.content)
