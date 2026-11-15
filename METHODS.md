# Methods

Draft; sections are added as each phase lands. The full one-page version comes in Phase 8.

## Capex per MW (k, F2/F3) — low confidence (n = 6)
- k = announced facility-only capex / Epoch IT MW, for 6 built sites whose company or government
  announcement names one figure for the same buildings Epoch tracks: Meta Kuna, Jeffersonville,
  Rosemount, Aiken, Temple; Google Mesa (phase 1). Per-site rows and links: `data/precedent_capex.csv`.
- low / median / high (10th / 50th / 90th percentile): **4.49 / 4.88 / 6.43 $M per IT MW**
  (`data/precedent_k_summary.csv`, from `pipeline/precedent_k.py`).
- Low confidence: six sites, five from one company with a repeated $800M figure.
- Epoch's modeled 37.88 $M per IT MW includes compute (chips). It is a different basis from k and
  is used only for announced capex that includes compute, or whose basis is unstated (low and
  median scenarios), per the owner's rule of 2026-11-15.
