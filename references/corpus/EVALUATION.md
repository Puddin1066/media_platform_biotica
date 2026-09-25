# Corpus evaluation

Before adding embeddings, compare scripts generated with the corpus disabled
(`SATOSHI_CORPUS_ENABLED=false`) against scripts generated with the same topic,
research budget, model, and format with corpus conditioning enabled.

Blind the pair labels before scoring.

Score each script 1-5 on:
- hook;
- coherence;
- evidence handling;
- originality;
- audience fit.

Run:

```sh
python3 corpus_eval.py --scorecard references/corpus/eval-scorecard.json
```

The first gate is simple: corpus-conditioned writing should improve the overall
mean. If it does not, improve the corpus/profile rather than adding embeddings.

If it does improve, a later embedding experiment compares:
1. deterministic tag retrieval;
2. semantic embedding retrieval.

Embeddings only ship if they add value over the simpler selector.
