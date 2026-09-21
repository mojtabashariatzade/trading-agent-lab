"""Read-only daily work preview. Never launches workers or writes state.

State evidence references are declarations, not fetched/verified GitHub evidence.
The coordinator must reconcile them with actual artifacts before execution.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path

STATES = {'QUEUED', 'WORKING', 'REVIEW', 'BLOCKED', 'DONE', 'CANCELLED'}
ACTIVE = {'WORKING', 'REVIEW'}
ROOT = Path(__file__).resolve().parents[1]


def validate(plan: dict, state: dict) -> dict[str, dict]:
    if plan.get('schema_version') != '1.0' or state.get('schema_version') != '1.0':
        raise ValueError('Unsupported schema version')
    if state.get('plan_id') != plan.get('plan_id'):
        raise ValueError('State belongs to a different plan')
    first, last = date.fromisoformat(plan['start_date']), date.fromisoformat(plan['end_date'])
    if last < first:
        raise ValueError('Invalid plan date range')
    tasks = {}
    for task in plan['tasks']:
        ident = task['id']
        if not isinstance(ident, str) or not ident or ident in tasks:
            raise ValueError('Duplicate or invalid task id')
        if task['priority'] not in {'P1', 'P2', 'P3', 'P4'} or task['lane'] not in {'product', 'research'}:
            raise ValueError('Invalid priority or lane')
        if task.get('state', 'QUEUED') != 'QUEUED':
            raise ValueError('Mutable task status belongs in delivery_state.json')
        if not task.get('title') or not task.get('acceptance'):
            raise ValueError('Task needs a title and acceptance evidence')
        if date.fromisoformat(task['planned_finish']) < date.fromisoformat(task['planned_start']):
            raise ValueError('Task finishes before it starts')
        tasks[ident] = task
    visiting, visited = set(), set()
    def visit(ident):
        if ident not in tasks:
            raise ValueError('Unknown dependency: ' + ident)
        if ident in visiting:
            raise ValueError('Dependency cycle')
        if ident in visited:
            return
        visiting.add(ident)
        for dependency in tasks[ident]['depends_on']:
            visit(dependency)
        visiting.remove(ident)
        visited.add(ident)
    for ident in tasks:
        visit(ident)
    rows = plan['days']
    expected = (last - first).days + 1
    if len(rows) != expected:
        raise ValueError('One daily row is required for each calendar day')
    for offset, row in enumerate(rows):
        if row['day'] != offset + 1 or date.fromisoformat(row['date']).toordinal() != first.toordinal() + offset:
            raise ValueError('Daily rows are not consecutive')
        for lane in ('product', 'research'):
            if row[lane] not in tasks or tasks[row[lane]]['lane'] != lane:
                raise ValueError('Daily row references an invalid task/lane')
    records = state.get('records', {})
    if set(records) - set(tasks):
        raise ValueError('State contains an unknown task')
    for ident, record in records.items():
        status = record.get('state')
        if status not in STATES:
            raise ValueError('Invalid state')
        evidence = record.get('evidence', [])
        if status == 'DONE' and (not isinstance(evidence, list) or not evidence or
                                 not all(isinstance(e, str) and e.strip() for e in evidence) or
                                 not record.get('completed_at')):
            raise ValueError('DONE needs a completion time and evidence reference')
        if status in ACTIVE and (not record.get('executor') or not record.get('started_at')):
            raise ValueError('Active work needs its real executor and start time')
        if status == 'BLOCKED' and not record.get('blocker'):
            raise ValueError('BLOCKED needs a specific reason')
        for field in ('started_at', 'completed_at'):
            if record.get(field):
                stamp = datetime.fromisoformat(record[field].replace('Z', '+00:00'))
                if stamp.tzinfo is None or stamp.utcoffset() is None:
                    raise ValueError('Recorded times must be timezone-aware')
    for lane in ('product', 'research'):
        count = sum(records.get(t['id'], {}).get('state') in ACTIVE for t in tasks.values() if t['lane'] == lane)
        if count > plan['limits'][lane] or plan['limits'][lane] != 1:
            raise ValueError('WIP limit exceeded or changed')
    return tasks


def preview(plan: dict, state: dict, on: date) -> dict:
    tasks = validate(plan, state)
    records = state.get('records', {})
    state_date = date.fromisoformat(state['as_of_date'])
    if state_date > on:
        raise ValueError('Cannot use a future state snapshot for a past preview')
    for record in records.values():
        for field in ('started_at', 'completed_at'):
            if record.get(field):
                stamp = datetime.fromisoformat(record[field].replace('Z', '+00:00')).astimezone(timezone.utc)
                if stamp.date() > on:
                    raise ValueError('Future work evidence cannot determine past readiness')
    def status(ident):
        return records.get(ident, {}).get('state', 'QUEUED')
    due, blocked, overdue, missing = [], [], [], {}
    for ident, task in tasks.items():
        if status(ident) in {'DONE', 'CANCELLED'} or task['planned_start'] > on.isoformat():
            continue
        due.append(task)
        needs = [d for d in task['depends_on'] if status(d) != 'DONE']
        if needs or status(ident) == 'BLOCKED':
            missing[ident] = needs
            blocked.append({'id': ident, 'dependencies': needs, 'reason': records.get(ident, {}).get('blocker')})
        if task['planned_finish'] < on.isoformat():
            overdue.append(ident)
    selected, interrupts, pulled_forward = {}, [], []
    for lane in ('product', 'research'):
        active = [t for t in tasks.values() if t['lane'] == lane and status(t['id']) in ACTIVE]
        ready = sorted((t for t in due if t['lane'] == lane and t['id'] not in missing and status(t['id']) == 'QUEUED'),
                       key=lambda t: (t['priority'], t['planned_start'], t['id']))
        if active:
            current = active[0]
            selected[lane] = current['id']
            interrupts.extend(t['id'] for t in ready if t['priority'] == 'P1' and current['priority'] != 'P1')
        else:
            if not ready:
                ready = sorted((t for t in tasks.values() if t['lane'] == lane
                                and status(t['id']) == 'QUEUED'
                                and t['planned_start'] > on.isoformat()
                                and all(status(d) == 'DONE' for d in t['depends_on'])),
                               key=lambda t: (t['priority'], t['planned_start'], t['id']))
                if ready:
                    pulled_forward.append(ready[0]['id'])
            selected[lane] = ready[0]['id'] if ready else None
    return {'plan_id': plan['plan_id'], 'date': on.isoformat(),
            'nominal_day': next((r for r in plan['days'] if r['date'] == on.isoformat()), None),
            'selected': selected, 'blocked': blocked, 'overdue_original_targets': sorted(overdue),
            'interrupt_at_safe_checkpoint': interrupts, 'pulled_forward': pulled_forward,
            'state_snapshot_date': state['as_of_date'], 'state_is_stale': state_date < on,
            'evidence_status': 'REFERENCES_ONLY_REVALIDATE_IN_GITHUB',
            'mode': 'READ_ONLY_PREVIEW_NO_WORKER_STARTED'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT / 'planning/delivery_plan.json')
    parser.add_argument('--state', type=Path, default=ROOT / 'planning/delivery_state.json')
    parser.add_argument('--date', default=datetime.now(timezone.utc).date().isoformat())
    args = parser.parse_args()
    try:
        result = preview(json.loads(args.plan.read_text()), json.loads(args.state.read_text()), date.fromisoformat(args.date))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
