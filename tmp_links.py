import csv
import json
import os

input_file = os.path.join('data', 'links.csv')
output_file = os.path.join('src', 'frontend', 'public', 'imdb_links.json')

links = {}
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # imdbId in ml-32m might have leading zeroes like 0114709. 
        # DictReader reads as string which preserves them, so we just map directly.
        links[row['movieId']] = row['imdbId']

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(links, f)

print(f"Generated JSON with {len(links)} entries.")
