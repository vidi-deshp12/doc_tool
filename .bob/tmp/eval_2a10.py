import json

facts = json.load(open('generated/facts.json', encoding='utf-8'))
gt    = json.load(open('eval/ground_truth.json', encoding='utf-8'))

# ── 1. Unresolved entries ────────────────────────────────────────────────────
print('=== UNRESOLVED ENTRIES ===')
for u in facts['unresolved']:
    print('  what :', u['what'])
    print('  why  :', u['why'])
    print('  where:', u['where'])
    print()

# ── 2. Route nodes ───────────────────────────────────────────────────────────
route_nodes = [n for n in facts['nodes'] if n['type'] == 'route']
print(f'=== ROUTE NODES in facts.json: {len(route_nodes)} ===')
for r in sorted(route_nodes, key=lambda x: (x.get('method',''), x.get('full_path','') or '')):
    print(f"  {r.get('method','?'):7} {r.get('full_path') or r.get('name','?')}")

# ── 3. Handles edges ─────────────────────────────────────────────────────────
print()
handles = [e for e in facts['edges'] if e['type'] == 'handles']
print(f'=== HANDLES edges: {len(handles)} ===')
for e in sorted(handles, key=lambda x: x['from']):
    route_id   = e['from']
    handler_id = e['to']
    method_path = route_id.replace('route:', '')
    handler_name = handler_id.split('::')[-1]
    print(f"  {method_path:45} -> {handler_name}")

# ── 4. Ground truth ──────────────────────────────────────────────────────────
print()
gt_routes = gt['routes']
print(f'=== GROUND TRUTH ROUTES: {len(gt_routes)} ===')
for r in sorted(gt_routes, key=lambda x: (x['method'], x['path'])):
    print(f"  {r['method']:7} {r['path']}")

# ── 5. DEP edges: external remaining? ───────────────────────────────────────
print()
dep_edges = [e for e in facts['edges'] if e['type'] == 'depends_on']
still_external = [e for e in dep_edges if e['to'].startswith('external:')]
print(f'=== DEPENDS_ON edges: {len(dep_edges)} total, {len(still_external)} still external ===')
for e in still_external:
    print(f"  {e['from']}  ->  {e['to']}")
