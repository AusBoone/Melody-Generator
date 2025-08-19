# Style Weight Presets

This guide explains the preset style vectors shipped with Melody‑Generator and how their weight dimensions influence generated melodies.

## Embedding Dimensions

The compact style embedding uses three dimensions:

1. **Counterpoint Influence** – higher values encourage stepwise motion and strict voice‑leading reminiscent of Baroque practices.
2. **Harmonic Color** – emphasizes chromatic notes and extended chords common in jazz.
3. **Hook Density** – biases toward repetitive, catchy motifs typical of contemporary pop.

Each preset assigns a weight to these dimensions:

| Name     | Vector           | Characteristics |
|----------|-----------------|----------------|
| baroque  | `[1.0, 0.0, 0.0]` | Structured counterpoint with minimal chromaticism. |
| jazz     | `[0.0, 1.0, 0.0]` | Swing feel and rich seventh/extended chord tones. |
| pop      | `[0.0, 0.0, 1.0]` | Simple melodies with repetitive hooks and clear tonic focus. |
| blues    | `[0.5, 0.4, 0.1]` | Mixes expressive bends with moderate chromaticism. |
| chiptune | `[0.1, 0.8, 0.1]` | Bright timbres and syncopated runs inspired by retro game music. |

These vectors can be extended at runtime using `load_styles` with a JSON or YAML file. Any additional vectors must keep the same dimensionality.

## Usage Examples

### Command Line

```bash
python -m melody_generator.cli --key C --chords C,G,Am,F --bpm 120 \
    --timesig 4/4 --notes 16 --output out.mid --style jazz
```

Selecting the `jazz` preset increases the likelihood of chromatic passing tones and syncopated rhythms.

### Programmatic Control

```python
from melody_generator import generate_melody, blend_styles, set_style

# Bias toward the baroque preset
set_style([1.0, 0.0, 0.0])
melody = generate_melody("C", 16, ["C", "G", "Am", "F"])

# Blend jazz and pop equally for a fusion style
hybrid = blend_styles("jazz", "pop", 0.5)
set_style(hybrid)
melody_fusion = generate_melody("C", 16, ["C", "G", "Am", "F"])
```

Adjusting the active vector subtly steers note selection; higher jazz weights yield more tension and chromaticism, whereas pop weights emphasise repetitive, singable lines.

---

For a deeper discussion of the embedding approach, see `README_ML_CONCEPTS.md`.
