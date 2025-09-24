# Melody-Generator for Classical Musicians

<!--
Summary:
- Expanded the overview so classically trained readers understand how each control maps to tonal-function concepts.
- Documented the generator's handling of cadences, species-style counterpoint, and motivic development with concrete musical vocabulary.
- Added practical checklists for adapting the output to rehearsal, ear-training, and composition workflows.
-->

This short guide introduces Melody-Generator from the viewpoint of a
classically trained performer or composer. It focuses on the musical capabilities
of the tool rather than its implementation details, translating interface
controls into familiar terminology such as tonic prolongation, cadence types and
species-style voice-leading expectations.

## Contents

1. [Goals and Philosophy](#goals-and-philosophy)
2. [Working With the Generator](#working-with-the-generator)
3. [Practical Applications](#practical-applications)
4. [Musical Output in Context](#musical-output-in-context)

## Goals and Philosophy

Melody-Generator aims to produce stylistically coherent lines that obey familiar
voice-leading conventions. Motifs are repeated and varied much like themes in
binary, ternary and rounded-binary forms. Large leaps are tempered by contrary
motion so phrases maintain a natural contour.

- **Tonal Function Awareness** – The engine distinguishes between tonic,
  predominant and dominant contexts. On downbeats it prioritises chord tones
  that articulate those functions, reinforcing authentic and half cadences.
- **Species Counterpoint Influence** – Successive intervals follow first- and
  second-species guidelines: dissonances are placed on weak beats, sevenths are
  prepared and resolved downward, and parallel perfect consonances are avoided
  unless intentionally enabled.
- **Motivic Development** – Generated motifs undergo sequence, inversion-lite
  motion and rhythmic augmentation/diminution to emulate the developmental
  techniques used in Classical-era exposition and development sections.

## Working With the Generator

Each configuration option corresponds to a concrete musical decision. The
sections below outline the expected behaviour and include examples expressed in
scale-degree or Roman-numeral terms so you can predict the resulting melody.

- **Key and Mode** – Supply any major or minor key. Modal options apply the
  appropriate alterations (e.g., Dorian raises the sixth degree, Mixolydian
  lowers the seventh). When you choose *D minor (Dorian)* the engine maps the
  predominant area to G minor with a B♮ to preserve the raised sixth, leading to
  characteristic ii°–V progressions with Lydian colouring.
- **Chord Progressions** – Chords may be specified manually or generated
  automatically. Progressions follow common-practice harmony, so entering `I, vi,
  ii, V` in C major yields cadential 6–4 motion and an authentic cadence.
  Repeating the progression establishes a rounded-binary structure (A | A′) with
  simple dominant retransition material.
- **Rhythmic Patterns** – Built-in patterns emulate typical note durations and
  cadential gestures. For instance, selecting the *Sarabande* pattern inserts a
  dotted-quarter + eighth gesture on the second beat to recreate the dance's
  characteristic emphasis. Custom patterns accept fractional beats, letting you
  script hemiola or Lombard rhythms.
- **Phrase Structure** – The phrase planner sketches a basic tension arc using
  4- or 8-bar antecedent/consequent pairs. In an ABA′ form, section A concludes
  with a half cadence (scale degree ^2 or ^7 over V), section B modulates via the
  circle of fifths, and A′ returns with a PAC reinforced by ^2–^1 motion.
- **Humanised Playback** – The exported MIDI data includes a subtle crescendo and
  decrescendo along with timing jitter. Velocity shaping mirrors a classic
  hairpin: a mezzo-piano start, forte arrival at the climax, and diminuendo into
  the cadence. Delays remain within ±12 ms so ensemble practice tracks feel
  intentional rather than sloppy.

### Mapping Parameters to Musical Concepts

| Parameter | Musical Analogue | Notes |
|-----------|------------------|-------|
| `--key` / GUI Key | Establishes tonal centre and determines diatonic collection | Supports enharmonic spellings for orchestral parts (e.g., G♭ major vs. F♯ major). |
| `--chords` | Roman-numeral progression or figured-bass plan | Accepts mixture (e.g., ♭VI in major) and secondary dominants (`V/ii`). |
| `--mode` | Church/modern mode inflection | Alters scale-degree tendencies and cadential approach tones. |
| `--rhythm` | Rhythmic cell library | Patterns labelled after dance forms (gigue, sarabande) or generic (syncopated 3-3-2). |
| `--structure` | Formal layout (period, rounded binary, song form) | Determines where antecedent/consequent cadences fall. |
| **Harmony toggle** | Adds third/fifth or sixth above the melody | Observes spacing rules to avoid voice crossing with the melody. |

#### Modal Voice-Leading Tips

- In **Dorian** contexts, the raised sixth (^6) prefers stepwise descent to the
  dominant (^5). Treat it as a consonant neighbour when harmonising against a iv
  chord.
- In **Phrygian**, the lowered second (^♭2) leads naturally to a Phrygian half
  cadence. Use it on weak beats to avoid accented cross-relations.
- **Mixolydian** melodies often conclude with a ♭7–1 plagal gesture; enable the
  *plagal cadence* option in the GUI to hear this resolution.

## Practical Applications

Classical musicians might use the generator to quickly produce sight-reading
material, to sketch counterpoint exercises or to seed improvisation sessions.
The tool intentionally avoids dense theoretical requirements so that performers
can adapt the results by ear or through simple edits in a notation program.

- **Sight-Reading Anthologies** – Generate 16-bar periods in remote keys (e.g.,
  E♭ minor) and print them as daily études. The motivic consistency keeps the
  material musical while the unexpected modulations challenge intonation and
  clef reading.
- **Counterpoint Drills** – Enable the *Counterpoint* toggle to receive a second
  species line that avoids hidden fifths and resolves sevenths correctly. Use it
  as a cantus firmus substitute in lesson plans.
- **Improvisation Seeds** – Export a lead sheet with the chord progression and
  generated melody, then ask students to improvise alternative consequents or to
  reharmonise the B section using secondary dominants.
- **Ear-Training** – Because the engine labels MIDI tracks with scale-degree
  metadata, instructors can create dictation exercises that emphasise specific
  leaps (e.g., ^4→^2 in deceptive cadences) by filtering events in a DAW.
- **Arranging & Orchestration** – Generated lines stay within a ninth around the
  specified octave. When orchestrating, assign the melody to winds or strings in
  their comfortable tessitura, then thicken cadences with brass doubling on tonic
  and dominant scale degrees.

## Musical Output in Context

The generator writes standard ``.mid`` files. These contain one or more melody
tracks along with optional harmony or counterpoint parts. Understanding how the
engine treats cadences, dissonance and articulations helps you integrate the
output into an ensemble or theory curriculum.

- **Monophonic or light polyphony** – Default output is a single melody, though
  additional lines can be enabled for simple trio textures. The harmony line
  doubles the melody at the third or sixth and drops to a perfect consonance at
  cadences to echo two-part inventions.
- **Cadential Planning** – Antecedent phrases conclude with either a half cadence
  (V) or an imperfect authentic cadence (V–I with ^3 on top). Consequents reserve
  perfect authentic cadences by ensuring the soprano lands on ^1 over I and the
  bass ascends via 5–1. A plagal cadence option reharmonises the final bar as
  IV–I for hymn-style endings.
- **Dissonance Handling** – Accented passing tones follow traditional resolution
  rules: sevenths resolve downward, augmented seconds (e.g., in harmonic minor)
  are respelled enharmonically to preserve melodic smoothness, and appoggiaturas
  occur only when tension weighting is high.
- **Expressive shaping** – MIDI velocities rise and fall in a gentle arc so the
  phrase feels performed rather than rigidly mechanical. Downbeat accents are +6
  velocity units stronger than upbeats, approximating classical bowing patterns.
- **Ornamentation Hooks** – Grace-note placeholders (MIDI channel 2) mark where
  you can add trills or mordents. When exporting to notation software you can
  replace these with actual ornaments.
- **Immediate playback** – Files open directly in notation software or any DAW
  that supports General MIDI. Use the `harpsichord` program for Baroque-style
  demos or swap to `clarinet` for wind rehearsals.
- **Flexible sketches** – Musicians can treat the result as a starting point for
  editing or improvisation, refining harmonies, adding suspensions or inserting
  modulation bridges.

Because General MIDI is used, the melodies import cleanly into nearly any
scorewriter. This makes the tool a quick way to generate sight-reading exercises
or new ideas for rehearsal while maintaining theoretical rigour.

---

In short, Melody-Generator provides a lightweight assistant that respects
traditional voice-leading while leaving room for personal interpretation.
