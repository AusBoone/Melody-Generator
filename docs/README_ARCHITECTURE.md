<!--
File: README_ARCHITECTURE.md
Purpose: Provide a high-level architecture overview for the Melody Generator project, including interfaces, core engine modules, platforms, and API interactions.
Usage: View in Markdown renderers that support Mermaid to visualize component relationships.
Assumptions: Diagram abstracts implementation details; consult module docs for specifics.
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

    subgraph CoreEngine["Core Melody Engine"]
        Harmony[Harmony Generator]
        Rhythm[Rhythm Engine]
        Sequence[Sequence Model]
        Style[Style Embeddings]
    end

    Interfaces --> CoreEngine
    CoreEngine --> MIDI[(MIDI Output)]
    MIDI --> Playback[Playback / FluidSynth]

    subgraph Platforms
        Local[Local Python Runtime]
        Server[Flask Server]
        Docker[Container Image]
    end

    Interfaces <--> Platforms
```

The CLI and desktop GUI execute locally, while the web interface exposes a REST-style API served by Flask. All interfaces delegate to the same core melody engine, which orchestrates harmony, rhythm, sequence modeling, and style embeddings before emitting MIDI for playback or export.
