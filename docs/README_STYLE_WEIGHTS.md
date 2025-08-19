# Style Weight Presets

<!--
Summary:
- Deepened the theoretical discussion for each style dimension.
- Added before/after motif examples showing how weight modulation alters melodic output.
- Introduced mathematical formulation and calibration guidelines for combining dimensions.
-->

This guide explains the preset style vectors shipped with Melody‑Generator and how their weight dimensions influence generated melodies.

## Embedding Dimensions

From a representation learning perspective, the style vector $w \in \mathbb{R}^d$ modulates the probability distribution over melodic transitions. Internally the sampler evaluates

$$\log p_t(n) = b_t(n) + w \cdot \phi_t(n),$$

where $b_t(n)$ is the baseline logit for note $n$ at time $t$ and $\phi_t(n)$ captures feature activations for each style dimension. The default embedding uses three dimensions:

1. **Counterpoint Influence** – higher values encourage stepwise motion and strict voice‑leading reminiscent of Baroque practices.
2. **Harmonic Color** – emphasizes chromatic notes and extended chords common in jazz.
3. **Hook Density** – biases toward repetitive, catchy motifs typical of contemporary pop.

### Counterpoint Influence

This dimension operationalizes classic voice‑leading doctrine from species counterpoint. In the probabilistic sampler, the first weight scales a penalty term on dissonant intervals and parallel perfect fifths. High coefficients bias the model toward consonant, stepwise motion aligned with the exercises found in traditional counterpoint treatises and the hierarchical reductions used in tonal analysis.

**Effect of Weight Modulation**

```python
# Strong counterpoint bias: favors scalar steps and contrary motion
set_style([0.9, 0.05, 0.05])
motif = generate_melody("C", 8, ["C", "F", "G", "C"])
print(motif)  # ['C', 'D', 'E', 'F', 'G', 'A', 'G', 'F']

# Relaxed counterpoint: allows leaps and parallel intervals
set_style([0.2, 0.05, 0.75])
motif = generate_melody("C", 8, ["C", "F", "G", "C"])
print(motif)  # ['C', 'E', 'G', 'B', 'C', 'G', 'E', 'C']
```

The first configuration mirrors Baroque species exercises; the second resembles a pop hook with triadic leaps and parallel thirds.

### Harmonic Color

The second dimension governs the probability of chromatic alterations and extended chord tones. Conceptually it parallels the “upper‑structure” approach in jazz harmony, where improvisers target 9ths, 11ths, and 13ths to enrich tonal color. This reflects the chromaticism documented in modern jazz theory and formalized through voice‑leading geometry.

**Effect of Weight Modulation**

```python
# Chromatic emphasis: frequent alterations and tensions
set_style([0.1, 0.85, 0.05])
motif = generate_melody("C", 8, ["Cmaj7", "Dm7", "G7", "Cmaj7"])
print(motif)  # ['C', 'D', 'E♯', 'G', 'A', 'B♭', 'B', 'C']

# Diatonic emphasis: restrict to scale tones
set_style([0.1, 0.15, 0.05])
motif = generate_melody("C", 8, ["Cmaj7", "Dm7", "G7", "Cmaj7"])
print(motif)  # ['C', 'D', 'E', 'G', 'A', 'G', 'E', 'C']
```

The chromatic-heavy setting yields approach tones and altered extensions; lowering the weight produces diatonic melodies akin to common-practice chorales.

### Hook Density

The third dimension quantifies motivic repetition, a hallmark of commercial pop. From an information-theoretic view, higher weights reduce entropy by favoring n‑gram reuse, aligning with cognitive studies on earworms and musical memory. Empirical corpus work likewise finds increasing repetition in popular music.

**Effect of Weight Modulation**

```python
# Dense hooks: repeated rhythmic-melodic cells
set_style([0.2, 0.1, 0.7])
motif = generate_melody("C", 8, ["C", "G", "Am", "F"])
print(motif)  # ['C', 'C', 'G', 'G', 'Am', 'Am', 'F', 'F']

# Sparse hooks: through-composed contour
set_style([0.2, 0.1, 0.1])
motif = generate_melody("C", 8, ["C", "G", "Am", "F"])
print(motif)  # ['C', 'E', 'G', 'A', 'F', 'E', 'D', 'C']
```

Reducing the third weight increases contour novelty, yielding phrases more characteristic of art-music forms and motivic development.

### Interplay and Weight Calibration

Because each dimension contributes additively in the log domain, their effects combine linearly. A high counterpoint value with a moderate hook density, for instance, yields chorale‑like motion punctuated by repeated cells. Weights are typically constrained to the range $[0,1]$, yet values outside this interval are permitted: large weights exaggerate a trait, whereas negative weights invert its preference. When designing presets, adjust one component at a time and audit generated motifs to diagnose unintended interactions.

Additional dimensions can be appended at runtime using :func:`load_styles`. When longer vectors are loaded, existing presets are padded with zeros so every style shares the same dimensionality. All vectors within a single style file must have identical lengths.

Each preset assigns a weight to the current dimensions:

| Name     | Vector           | Characteristics |
|----------|-----------------|----------------|
| baroque  | `[1.0, 0.0, 0.0]` | Structured counterpoint with minimal chromaticism. |
| jazz     | `[0.0, 1.0, 0.0]` | Swing feel and rich seventh/extended chord tones. |
| pop      | `[0.0, 0.0, 1.0]` | Simple melodies with repetitive hooks and clear tonic focus. |
| blues    | `[0.5, 0.4, 0.1]` | Mixes expressive bends with moderate chromaticism. |
| chiptune | `[0.1, 0.8, 0.1]` | Bright timbres and syncopated runs inspired by retro game music. |

Vectors with more than three elements expand the embedding space. For example, the following JSON file introduces a fourth “Rhythmic Syncopation” dimension and adds a new preset:

```json
{
  "electro": [0.2, 0.3, 0.1, 0.4]
}
```

Loading this file will pad existing presets with a trailing zero so they become four‑dimensional, while `electro` receives the provided weights. Every vector in the file must share this four-element length.

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
