<!-- Expanded training documentation with genre-specific datasets, preprocessing,
     weight tuning, loss curve guidance, extension tips, and music-theory links -->

# Training Larger Models

This guide describes how to train more expressive machine learning models on
multi-genre MIDI datasets. Each genre receives its own checkpoint so the
runtime system can bias note selection toward stylistic patterns.

## Dataset Layout

The training script expects a directory structure similar to::

    data_root/
        jazz/
            file1.mid
            file2.mid
        rock/
            song1.mid
            song2.mid

Each subfolder represents a genre and contains MIDI files used for that
style. Additional genres can be added as new subdirectories.

## Genre-Specific Dataset Selection

Choosing high-quality data for each genre is critical for convincing musical
output. A few suggestions:

* **Jazz** – favor improvisations and lead sheets that highlight extended
  harmonies and swing rhythms.
* **Rock** – include guitar-driven riffs and steady percussion to capture
  backbeat emphasis.
* **Blues** – assemble classic 12-bar progressions that prominently feature
  the blues pentatonic scale and call-and-response motifs.
* **Classical** – use well-edited scores with clear phrasing and dynamics to
  model long-form structure.

Balancing dataset size across genres helps the optimiser avoid biasing toward
the largest style.

## Preprocessing Steps

Before training, the ``train_multi_genre`` script performs several cleaning
operations:

1. **Validation** – skips corrupted or non-MIDI files.
2. **Quantisation** – snaps note onsets to a fixed grid to simplify rhythm
   modelling.
3. **Transposition** – optionally shifts pieces to a common key (often C major
   or A minor) to reduce the number of pitch classes the model must learn.
4. **Velocity normalisation** – scales dynamics into a consistent range so the
   network does not overfit to recording artefacts.
5. **Chunking** – splits long performances into shorter sequences for efficient
   batching.

These steps produce uniform training examples while preserving stylistic cues.

## Running Training

Use the :mod:`scripts.train_multi_genre` helper to fit either a Transformer
or variational autoencoder model for each genre:

```bash
python scripts/train_multi_genre.py \
    --data-root /path/to/data_root \
    --genres jazz rock classical \
    --model transformer \
    --epochs 20 \
    --checkpoint-dir models
```

Checkpoints are written as ``{genre}.pt`` into ``models`` by default. These
files can be selected at runtime via the CLI using ``--genre`` and
``--model-dir``.

## Weight Tuning Rationale

Hyperparameters such as learning rate, sequence length and style-specific loss
weights can heavily influence convergence. Start with conservative values
before experimenting:

* Increase ``--sequence-length`` to expose the model to longer phrases at the
  cost of memory.
* Adjust ``--kl-weight`` when training the variational autoencoder to balance
  reconstruction fidelity and latent-space regularisation.
* Raise ``--style-weight`` for genres with sparse data so their checkpoints do
  not underfit.

Carefully logging these choices makes it easier to reproduce favourable
results.

## Monitoring Training

Track losses for each genre to spot instability early. Record epoch losses to a
CSV file and plot the results with ``matplotlib`` or another visualisation tool
to produce loss curves for each style.

## Runtime Selection

When invoking the command-line generator, specify ``--enable-ml`` and
optionally ``--genre`` to bias toward a particular style:

```bash
python -m melody_generator.cli --enable-ml --genre jazz --model-dir models ...
```

If the requested genre checkpoint is missing or corrupt, the application
falls back to an untrained model so generation still succeeds.

## Extending to New Genres

To incorporate additional styles:

1. Gather a representative MIDI corpus for the new genre.
2. Add the genre name to the ``--genres`` list when invoking the training
   script.
3. Review the preprocessing pipeline for genre-specific quirks (e.g., unusual
   time signatures or tuning).
4. Tune hyperparameters using the monitoring guidance above.

Documenting these steps keeps experiments reproducible and simplifies
collaboration.

## Music-Theory-Informed Targets

Music theory can guide loss functions and evaluation metrics. For blues, the
target distribution may emphasise the pentatonic scale degrees: 1, b3, 4, 5 and
b7. Rewarding predictions that remain within this set encourages recognisable
phrasing. Similar scale or chord constraints can be encoded for other genres to
reinforce stylistic expectations.
