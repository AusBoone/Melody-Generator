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

## Runtime Selection

When invoking the command-line generator, specify ``--enable-ml`` and
optionally ``--genre`` to bias toward a particular style:

```bash
python -m melody_generator.cli --enable-ml --genre jazz --model-dir models ...
```

If the requested genre checkpoint is missing or corrupt, the application
falls back to an untrained model so generation still succeeds.

## Extending

The provided training script focuses on clarity. For real projects consider
incorporating data augmentation, larger model architectures and longer
training schedules. The script serves as a starting point that can be
expanded to suit specific research goals.
