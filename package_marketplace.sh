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

echo "3b. Smoke testing engagement_analyzer.py..."
python3 "$MARKETPLACE_DIR/skills/engagement-audit/scripts/engagement_analyzer.py" --help > /dev/null
echo "   ✓ engagement_analyzer.py CLI test passed."

echo "3c. Smoke testing orchestrator.py & merge logic..."
python3 "$MARKETPLACE_DIR/skills/audit-orchestrator/scripts/orchestrator.py" --help > /dev/null
python3 -c "
import json, subprocess, tempfile, os, sys
d1 = {'site': 'ex.com', 'summary': {'total_findings': 2, 'critical': 1, 'high': 1, 'medium': 0, 'low': 0}, 'findings': [{'id': 'F-001', 'severity': 'critical', 'title': 'C1'}, {'id': 'F-002', 'severity': 'high', 'title': 'H1'}]}
d2 = {'site': 'ex.com', 'summary': {'total_findings': 1, 'critical': 0, 'high': 0, 'medium': 1, 'low': 0}, 'findings': [{'id': 'F-001', 'severity': 'medium', 'title': 'M1'}]}
f1, f2, out = tempfile.NamedTemporaryFile('w', delete=False), tempfile.NamedTemporaryFile('w', delete=False), tempfile.NamedTemporaryFile('w', delete=False)
json.dump(d1, f1); f1.close()
json.dump(d2, f2); f2.close()
out.close()
subprocess.run([sys.executable, '$MARKETPLACE_DIR/skills/audit-orchestrator/scripts/orchestrator.py', '--from-files', f1.name, f2.name, '--output', out.name, '--quiet'], check=True)
with open(out.name) as fp:
    res = json.load(fp)
assert res['summary']['total_findings'] == 3
assert res['summary']['critical'] == 1 and res['summary']['high'] == 1 and res['summary']['medium'] == 1 and res['summary']['low'] == 0
assert len(res['findings']) == 3
assert [f['id'] for f in res['findings']] == ['F-001', 'F-002', 'F-003']
os.remove(f1.name); os.remove(f2.name); os.remove(out.name)
print('   ✓ orchestrator.py CLI & merge test passed.')
"

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
