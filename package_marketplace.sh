#!/usr/bin/env bash
set -e

echo "=== Nexus Coders: Marketplace Packaging & Validation ==="

MARKETPLACE_DIR="nexus-coders-brand-audit"
ZIP_NAME="nexus-coders-brand-audit.zip"

if [ ! -d "$MARKETPLACE_DIR" ]; then
    echo "Error: $MARKETPLACE_DIR directory not found!"
    exit 1
fi

echo "1. Validating marketplace.json manifest..."
python3 -c "
import json
with open('$MARKETPLACE_DIR/marketplace.json') as f:
    data = json.load(f)
assert 'name' in data and 'version' in data and 'skills' in data
entrypoints = [s for s in data['skills'] if s.get('entrypoint') is True]
assert len(entrypoints) == 1, f'Expected exactly 1 entrypoint, found {len(entrypoints)}'
print(f'   ✓ Manifest valid. Entrypoint: {entrypoints[0][\"id\"]}')
"

echo "2. Validating skills according to agentskills.io format..."
python3 -c "
import json, os
with open('$MARKETPLACE_DIR/marketplace.json') as f:
    data = json.load(f)

for skill in data['skills']:
    skill_path = os.path.join('$MARKETPLACE_DIR', skill['path'])
    skill_md = os.path.join(skill_path, 'SKILL.md')
    assert os.path.isfile(skill_md), f'Missing SKILL.md in {skill_path}'
    with open(skill_md, 'r', encoding='utf-8') as f:
        content = f.read()
    assert content.startswith('---'), f'{skill_md} missing YAML frontmatter start'
    assert 'name:' in content, f'{skill_md} missing name frontmatter'
    assert 'description:' in content, f'{skill_md} missing description frontmatter'
    print(f'   ✓ Skill valid: {skill[\"id\"]}')
"

echo "3. Smoke testing crawler.py..."
python3 "$MARKETPLACE_DIR/skills/discoverability-audit/scripts/crawler.py" --help > /dev/null
echo "   ✓ crawler.py CLI test passed."

echo "4. Generating $ZIP_NAME..."
rm -f "$ZIP_NAME"
# Zip the marketplace contents per Adobe guidelines
cd "$MARKETPLACE_DIR"
zip -r "../$ZIP_NAME" . -x "*.pyc" -x "*__pycache__*" -x "*.DS_Store"
cd ..

ZIP_SIZE=$(stat -c%s "$ZIP_NAME" 2>/dev/null || stat -f%z "$ZIP_NAME")
ZIP_SIZE_MB=$(echo "scale=2; $ZIP_SIZE / 1048576" | bc)
echo "   ✓ Generated $ZIP_NAME ($ZIP_SIZE_MB MB / $ZIP_SIZE bytes)"

if [ "$ZIP_SIZE" -gt 52428800 ]; then
    echo "ERROR: Zip file exceeds 50 MB contest limit!"
    exit 1
else
    echo "   ✓ Submission size within 50 MB limit."
fi

echo "=== Validation & Packaging Complete! Ready for Submission ==="
