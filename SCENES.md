# Spec reference

An episode is `episodes/<NNN-slug>/spec.json`. Copy `episodes/002-peak-end/spec.json` and change it.

```json
{
  "id": "003-moments-of-truth",
  "title": "50 million moments of truth",      // also the output file name
  "series": "HOSPITALITY 101",
  "voice": {"sid": 3, "speed": 1.12},           // Kokoro af_heart; keep these
  "cover_t": 2.4,                               // optional: which second becomes the cover image
  "scenes": [ { ...scene... }, ..., {"type": "end", "lines": [[...sign-off...]]} ]
}
```

## Scenes

```json
{
  "label": "THE EXPERIMENT",            // small mono label under HOSPITALITY 101 (optional)
  "lines": [                             // narration, in order
    ["text the voice reads", "caption with *gold* words\nand a line break", 0.4]   // last = pause after (s)
  ],
  "elements": [ ... ],
  "sfx": [{"type": "boom", "at": "chose"}],   // whoosh between scenes and pops on icons are automatic
  "camera": {"push": 0.04, "cy": 920},         // slow zoom over the scene
  "auto_pops": true
}
```

- The voice text and caption can differ: write numbers as words in the voice text ("nineteen ninety-three") and as digits in the caption ("*1993*").
- "Qarya" is pronounced automatically ("Karya"); keep the brand spelling everywhere.
- A scene starts ~0.3 s before its first line and ends when the next scene starts.
- Keep captions to 2 short lines (≈ 30 characters each). Gold-highlight 1–2 key words per caption.
- The last scene is always `{"type": "end", "lines": [["Follow Qarya, for more hospitality literacy.", "Follow Qarya for more\n*Hospitality Literacy.*", 2.2]]}`.

## Time references (`at`, `out`, `hl_at`, `dim_at`)

| value | meaning |
|---|---|
| `0.4` | seconds after the scene starts |
| `"L1"` / `"L1.end"` | start / end of the scene's 2nd line (0-based) |
| `"water"` / `"water#2"` | when the narrator says "water" (2nd time) in this scene; numbers work as words ("sixty") |
| `"@end"` / `"@start"` | scene end / start |
| `"water+0.3"`, `"L2-0.2"` | any of the above with an offset |

If a word isn't heard by the recogniser the time is estimated from the script and a `[timing]` note is printed; check the preview.

## Layout (1080 × 1920)

- y 400–500: label (centre) and watermark (top-right). Keep elements below y 560.
- y 560–1330: art zone. Centre of attention ≈ y 880.
- y 1360–1520: captions. Nothing important here.
- x 90–990 safe width. Two columns: x 300 and x 780. Three: x 240 / 540 / 840.

## Elements

| el | key params | notes |
|---|---|---|
| `icon` | `name`, `x`, `y`, `size` (320), `anim` pop/rise/drop, `float` (8), `wobble` (2), `rot`, `glow` (true/false/colour), `style` ink/mono, `ink` | Fluent emoji restyled. Find names: `python3 kit/icons.py search <word>`; preview: `python3 kit/icons.py sheet out.jpg "Ice" "Key"` |
| `text` | `t`, `x`, `y`, `size` (72), `font` serif/serif_i/sans/sansb/bold/mono/monob, `color`, `hl`, `anim` rise/pop/none, `max_w` (920, auto-shrinks), `tracking`, `upper`, `box` (pill background) | `*word*` = highlight colour |
| `panel` | `x`, `y`, `w`, `h`, `tone` dark/cream, `hl_at` (gold outline), `dim_at` | card behind other elements |
| `dots` | `n`, `cols`, `gap`, `r`, `x`, `y`, `hl`, `hl_at`, `hl_dur` | "22 of 32 people" |
| `number` | `value`, `from`, `x`, `y`, `size`, `prefix`, `suffix`, `decimals`, `dur` | count-up |
| `curve` | `box` [x0,y0,x1,y1], `pts` [[u,v]…] (0–1, v up), `dur`, `color`, `xlabel`, `ylabel`, `markers` [{u,label,color,at,side}] | line chart drawn left to right |
| `bar` | `x` (left), `y`, `w`, `h`, `frac`, `color`, `dur` | horizontal bar |
| `arrow` | `from` [x,y], `to` [x,y], `bend`, `dashed`, `color`, `dur` | |
| `check` / `cross` | `x`, `y`, `size` | animated tick / cross |
| `clock` | `x`, `y`, `r`, `from` "11:00", `to` "15:00", `delay`, `dur` | |
| `burst` | `x`, `y`, `r`, `color` | one-off radial flash |
| `particles` | `kind` snow/dust/sparkle/bubbles, `n`, `box` | ambient |

Colours: cream, gold, goldhi, rose, teal, sky, navy, mauve, grey, dim.
SFX types: whoosh, boom, shimmer, pop, tick.
