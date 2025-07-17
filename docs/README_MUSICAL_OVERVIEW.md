# Melody-Generator for Classical Musicians

This short guide introduces Melody-Generator from the viewpoint of a
classically trained performer or composer. It focuses on the musical capabilities
of the tool rather than its implementation details.

## Contents

1. [Goals and Philosophy](#goals-and-philosophy)
2. [Working With the Generator](#working-with-the-generator)
3. [Practical Applications](#practical-applications)
4. [Musical Output in Context](#musical-output-in-context)

## Goals and Philosophy

Melody-Generator aims to produce stylistically coherent lines that obey familiar voice-leading conventions. Motifs are repeated and varied much like themes in classical forms. Large leaps are tempered by contrary motion so phrases maintain a natural contour.

## Working With the Generator

- **Key and Mode** – Supply any major or minor key. Modes such as Dorian and Mixolydian are also available to evoke folk or early music flavours.
- **Chord Progressions** – Chords may be specified manually or generated automatically. Progressions follow common-practice harmony and can be repeated to create simple forms.
- **Rhythmic Patterns** – Built-in patterns emulate typical note durations (eighths, quarters, etc.). You can provide your own pattern to mimic a particular style.
- **Phrase Structure** – The phrase planner sketches a basic tension arc so melodies rise and fall in a predictable shape. Sections can repeat in forms like AABA or ABA'.
- **Humanised Playback** – The exported MIDI data includes a subtle crescendo and decrescendo along with timing jitter. This yields a more expressive performance when auditioning the melody.

## Practical Applications

Classical musicians might use the generator to quickly produce sight-reading material, to sketch counterpoint exercises or to seed improvisation sessions. The tool intentionally avoids dense theoretical requirements so that performers can adapt the results by ear or through simple edits in a notation program.

## Musical Output in Context

The generator writes standard ``.mid`` files. These contain one or more melody
tracks along with optional harmony or counterpoint parts.

- **Monophonic or light polyphony** – Default output is a single melody, though
  additional lines can be enabled for simple trio textures.
- **Key and progression aware** – Notes follow the selected key and chord
  progression to maintain tonal coherence.
- **Expressive shaping** – MIDI velocities rise and fall in a gentle arc so the
  phrase feels performed rather than rigidly mechanical.
- **Immediate playback** – Files open directly in notation software or any
  DAW that supports General MIDI.
- **Flexible sketches** – Musicians can treat the result as a starting point for
  editing or improvisation, refining harmonies or adding ornamentation.

Because General MIDI is used, the melodies import cleanly into nearly any
scorewriter. This makes the tool a quick way to generate sight-reading exercises
or new ideas for rehearsal.

---

In short, Melody-Generator provides a lightweight assistant that respects traditional voice-leading while leaving room for personal interpretation.
