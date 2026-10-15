"""Retrieval used in the downstream QA evaluation: 240-word passages, BM25 (k1=1.2, b=0.75), and a dense
retriever (BAAI/bge-small-en-v1.5, normalized CLS embeddings, cosine similarity, query instruction prefix)."""
import collections
import heapq
import math
import re

TOKEN = re.compile(r"\w+")
CHUNK_WORDS = 240
TOP_K = 5
DENSE_MODEL = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def tokens(t):
    return TOKEN.findall(t.lower())


def passages(corpus):
    """corpus: iterable of {"family", "vid", "title", "text"} in a stable order; body is split without overlap."""
    out = []
    for d in corpus:
        w = d["text"].split()
        for start in range(0, len(w), CHUNK_WORDS):
            out.append(dict(d, text=" ".join(w[start:start + CHUNK_WORDS]), offset=start))
    return out


class BM25:
    def __init__(self, docs):
        self.docs = docs
        self.postings = collections.defaultdict(list)
        lengths = []
        for i, d in enumerate(docs):
            ts = tokens(d["text"])
            lengths.append(len(ts))
            for word, n in collections.Counter(ts).items():
                self.postings[word].append((i, n))
        self.n = len(docs)
        avg = sum(lengths) / max(1, self.n)
        self.norm = [1.2 * (1 - .75 + .75 * l / avg) for l in lengths]
        self.idf = {w: math.log(1 + (self.n - len(p) + .5) / (len(p) + .5)) for w, p in self.postings.items()}

    def search(self, q, k=TOP_K):
        scores = collections.defaultdict(float)
        for word in sorted(set(tokens(q))):
            for i, tf in self.postings.get(word, []):
                scores[i] += self.idf[word] * tf * 2.2 / (tf + self.norm[i])
        top = heapq.nsmallest(k, scores, key=lambda i: (-scores[i], i))
        if len(top) < k:  # ties and zero scores fall back to corpus order
            top.extend(i for i in range(self.n) if i not in scores and len(top) < k)
        return [{**self.docs[i], "score": scores.get(i, 0)} for i in top[:k]]


class DenseRetriever:
    def __init__(self, docs, model_dir=DENSE_MODEL, batch=24):
        import numpy as np
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.np, self.torch = np, torch
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModel.from_pretrained(model_dir).eval()
        self.docs = docs
        self.emb = np.concatenate([self.encode([d["text"] for d in docs[i:i + batch]]) for i in range(0, len(docs), batch)])

    def encode(self, texts, query=False):
        if query:
            texts = [QUERY_PREFIX + x for x in texts]
        enc = self.tok(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
        with self.torch.inference_mode():
            z = self.model(**enc).last_hidden_state[:, 0]
            z = self.torch.nn.functional.normalize(z, p=2, dim=1)
        return z.cpu().numpy().astype("float32")

    def search(self, q, k=TOP_K):
        s = self.emb @ self.encode([q], query=True)[0]
        top = sorted(range(len(s)), key=lambda i: (-float(s[i]), i))[:k]
        return [{**self.docs[i], "score": float(s[i])} for i in top]
