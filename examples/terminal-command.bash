python scripts/build_proposal_from_mmk.py \
  --input input_files/nicky-boiardi.html \
  --type skippered \
  --lead input_files/nicky-boiardi.json \
  --fetch-images \
  --output output_files/nicky-boiardi-out.json \
  --upload

# Build from CSV (no HTML needed — filters yachts from yacht_database_full.csv)
python scripts/build_proposal_from_csv.py \
  --lead input_files/hollie-pollak.json \
  --output output_files/hollie-pollak-out.json \
  --upload