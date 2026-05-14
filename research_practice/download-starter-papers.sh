#!/bin/bash
# Research OS — Starter Papers Download Script
# Run this once to populate inbox/ with the three foundational papers.
# Requires: curl (preinstalled on macOS and Linux)
#
# Usage:
#   chmod +x download-starter-papers.sh
#   ./download-starter-papers.sh
#
# All three papers are open-access on arXiv.

set -e
cd "$(dirname "$0")/inbox"

echo "Downloading starter papers to inbox/..."
echo ""

echo "[1/3] Kirkpatrick et al. (2017) — Overcoming Catastrophic Forgetting (EWC)"
curl -L -o "01_kirkpatrick_2017_ewc.pdf" "https://arxiv.org/pdf/1612.00796"

echo "[2/3] Ha & Schmidhuber (2018) — World Models"
curl -L -o "02_ha_schmidhuber_2018_world_models.pdf" "https://arxiv.org/pdf/1803.10122"

echo "[3/3] Pellegrini et al. (2019) — Latent Replay for Real-Time Continual Learning"
curl -L -o "03_pellegrini_2019_latent_replay.pdf" "https://arxiv.org/pdf/1912.01100"

echo ""
echo "Done. Three papers in inbox/."
echo ""
echo "Next: read in this order, then run Layer 1 extraction on each."
echo "  1. Ha & Schmidhuber (start with worldmodels.github.io for the interactive)"
echo "  2. Kirkpatrick (EWC)"
echo "  3. Pellegrini (Latent Replay)"
echo ""
echo "Suggested cadence:"
echo "  Day 1: Read paper 1, write extracted/02_ha_schmidhuber.md"
echo "  Day 3: Read paper 2, write extracted/01_kirkpatrick.md"
echo "  Day 5: Read paper 3, write extracted/03_pellegrini.md"
echo "  Day 7: Run synthesis across all three, write briefs/01_procore_oec_v1.md"
