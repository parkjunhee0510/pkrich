# Research Lumi Pet Design

## Purpose

Create a Codex-compatible custom pet for the user, described in Korean as "리서치 루미".
The pet should reflect a calm Korean-language stock research workflow: daily evidence gathering,
cost-aware automation, source quality, and patient review.

## Approved Direction

The approved concept is "차분한 근거 탐색자".

리서치 루미 is a small charcoal research robot with a warm gold core and a small green signal
antenna. It should feel like a quiet research partner that lights up useful evidence in news,
filings, prices, and portfolio signals.

## Visual Style

- Style: soft sticker / small 3D toy hybrid, not strict pixel art.
- Silhouette: compact whole-body shape readable inside a small Codex pet cell.
- Palette: charcoal body, warm gold core, muted silver face panel, green signal antenna.
- Expression: focused, gentle, trustworthy, and not overly silly.
- Props: built-in light core and antenna only; avoid separate papers, UI panels, text, charts, or logos.
- Background during generation: flat removable chroma-key background.

## Animation Semantics

The final pet must support the Codex app's nine animation states:

- `idle`: quiet breathing, tiny blink, or subtle core glow.
- `running-right`: directional drag movement facing right, without speed lines or dust.
- `running-left`: left-facing counterpart, mirrored only if it preserves identity and timing.
- `waving`: small friendly hand or antenna gesture, no wave marks.
- `jumping`: body moves vertically, no shadow or floor effects.
- `failed`: dimmer core and disappointed expression, with no detached symbols.
- `waiting`: expectant approval-waiting posture distinct from idle.
- `running`: active analysis or processing posture, not literal jogging.
- `review`: focused evidence-checking posture with slight head tilt or lean.

## Output Contract

The production run should create a packaged Codex pet under the user's Codex home:

- `pet.json`
- `spritesheet.webp`

The generated atlas must remain compatible with the hatch-pet workflow:

- 1536x1872 transparent-capable atlas.
- 192x208 frame cells.
- All required rows are present and visually consistent.
- Contact sheet and preview GIFs are generated and visually checked.
- `qa/review.json` and `final/validation.json` have no blocking errors.

## Risks And Constraints

- The pet should not contain readable text, trading advice, ticker symbols, UI screenshots, or logos.
- The green antenna and gold core must stay visually distinct from the chroma-key background.
- Detached effects, shadows, speed lines, wave marks, dust, and glow halos should be avoided because
  they can break transparent sprite extraction.
- Existing repository changes are unrelated and should not be reverted or mixed into pet work.

## Completion Criteria

The task is complete when 리서치 루미 is packaged as a Codex pet, the final contact sheet/previews
are accepted, and the output paths are reported to the user in Korean.
