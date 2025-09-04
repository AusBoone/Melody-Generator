<!--
File: README_ARCHITECTURE.md
Purpose: Provide a high-level architecture overview for the Melody Generator project, including interfaces, core engine modules, platforms, data sources, and API interactions.
Usage: View in Markdown renderers that support Mermaid to visualize component relationships.
Assumptions: Diagram abstracts implementation details; consult module docs for specifics.

Update: Expanded the diagram and explanations to cover the validation layer, model and style data inputs, optional Celery worker, and the training pipeline that produces model artifacts.
-->

# Architecture Overview

This document outlines the major components of the Melody Generator system and how they interact. It is intended to give newcomers context on the project's structure and supported platforms.

```mermaid
flowchart TB
    subgraph Interfaces
        CLI[Command-Line Interface]
        GUI[Desktop GUI]
        WebGUI[Flask Web GUI / API]
    end

    subgraph Validation["Input Validation"]
        Params[Parameter Sanitization]
    end

    subgraph CoreEngine["Core Melody Engine"]
        Harmony[Harmony Generator]
        Rhythm[Rhythm Engine]
        Sequence[Sequence Model]
        Style[Style Embeddings]
        Melody[Melody Synthesizer]
    end

    subgraph Data["Model & Style Data"]
        Styles[Style Weight Files]
        Models[Sequence Model Weights]
        SoundFonts[(SoundFonts)]
    end

    Interfaces --> Validation --> CoreEngine
    Styles --> Style
    Models --> Sequence
    CoreEngine --> MIDI[(MIDI Output)]
    MIDI --> Playback[Playback / FluidSynth]
    SoundFonts --> Playback

    subgraph Platforms
        Local[Local Python Runtime]
        Server[Flask Server]
        Docker[Container Image]
        Worker[Celery Worker]
    end

    Interfaces <--> Platforms
    Platforms --> Data
```

The CLI and desktop GUI execute locally, while the web interface exposes a REST-style API served by Flask. All interfaces route through a validation layer that sanitizes user parameters before invoking the core melody engine. The engine orchestrates harmony, rhythm, sequence modeling, and style embeddings, drawing on external model and style data. It produces MIDI for playback or export, optionally previewed via FluidSynth. Model weights, style files, and soundfonts live outside the engine but are loaded on demand.

```mermaid
flowchart LR
    Dataset[(MIDI Dataset)] --> Preprocess[Preprocessing]
    Preprocess --> TrainSeq[Train Sequence Model]
    Preprocess --> TrainStyle[Train Style Embeddings]
    TrainSeq --> ModelWeights[Sequence Model Weights]
    TrainStyle --> StyleFiles[Style Weight Files]
```

Training artifacts such as sequence model weights and style embeddings are produced offline. The runtime architecture above consumes these generated files to bias note selection and timbre.
