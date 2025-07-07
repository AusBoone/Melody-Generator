# Machine Learning Concepts in Melody-Generator

This document surveys the statistical and deep learning techniques employed by the project. The explanations assume familiarity with graduate-level machine learning but require no prior knowledge of music theory.

## Markovian Note Selection

At its core the generator treats candidate notes at each step as a Markov state. Transition weights favour repeated pitches and stepwise motion, encoding prior musical knowledge without the need for training data. Large leaps are tracked and penalised to maintain a smooth contour.

## Sequence Models

The `SequenceModel` interface defines the contract for predictive models that bias note selection. A lightweight LSTM implementation demonstrates how learned probabilities can refine the otherwise rule-based process. The design allows alternative architectures such as Transformers or Temporal Convolutional Networks while keeping the surrounding code agnostic to the underlying model.

### Training and Fine Tuning

Example routines in `augmentation.py` illustrate data augmentation strategies (transposition, inversion and rhythmic perturbation) and a simple fine-tuning loop. Although the project ships without large pretrained weights, these functions highlight how one might adapt a small model to specific genres.

## PyTorch and Additional Dependencies

The optional neural modules rely on [PyTorch](https://pytorch.org) for tensor operations and gradient-based optimisation. When present, PyTorch powers the lightweight LSTM and style VAE used to bias candidate notes. If the library is missing, Melody-Generator gracefully falls back to purely heuristic weighting. Other dependencies include NumPy for efficient vector maths, Numba for just-in-time compilation of hot loops and ONNX Runtime for running exported models.

## Style Embeddings

A variational autoencoder (VAE) learns compact style vectors from MIDI corpora. The active vector can be set globally or supplied per-call to subtly influence note probabilities. Interpolating between vectors blends genres in a continuous manner.
Additional presets can be loaded using `load_styles`. Provide a JSON or YAML
file mapping style names to vectors and each entry will merge into the preset
dictionary. Example (``docs/example_styles.json``)::

    {
        "blues": [0.5, 0.4, 0.1],
        "chiptune": [0.1, 0.8, 0.1]
    }


## Tension Modelling

Musical tension is estimated via heuristics that map intervals to scalar tension values. When NumPy is available these computations are vectorised for efficiency. The resulting tension profile can modulate candidate weights so that generated phrases ebb and flow like a human performance.

## ONNX Export and Quantisation

Models derived from `SequenceModel` may be exported to ONNX for cross-platform inference. Dynamic quantisation produces an 8‑bit representation that greatly reduces file size and speeds up CPU execution. These features facilitate deployment in environments where installing full PyTorch is impractical.

---

By combining modest neural components with music-specific heuristics, Melody‑Generator remains lightweight yet extensible. Researchers can experiment with different architectures or training regimes simply by implementing the `SequenceModel` protocol and adjusting the weighting functions.
