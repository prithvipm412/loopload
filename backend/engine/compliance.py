"""Contract-defined demo compliance checks on plain planning dictionaries."""
from datetime import date


def check_leg(leg: dict, load: dict | None, truck: dict, config: dict) -> dict:
    issues=[]
    def issue(code, message, severity='error'):
        issues.append(dict(code=code,severity=severity,message=message))
    week_start=date.fromisoformat(config['week_start'][:10])
    permit=date.fromisoformat(truck['national_permit_valid_until'])
    if permit < week_start:
        issue('PERMIT_EXPIRED',f"National permit expired on {permit.isoformat()}")
    if leg['kind'] != 'empty' and load is not None:
        bill=load.get('eway_bill')
        if not bill and load['cargo_value_inr'] > config.get('eway_threshold_inr',50000):
            issue('EWAY_MISSING','E-way bill is required for this cargo value')
        if bill:
            if bill['valid_until_h'] < leg['arrive_h']:
                issue('EWAY_EXPIRES',f"E-way bill expires at {bill['valid_until_h']:g}h but delivery is planned at {leg['arrive_h']:g}h")
            if bill['vehicle_reg'] != truck['reg_no']:
                issue('EWAY_VEHICLE_MISMATCH','E-way bill vehicle differs from the truck; update Part B','warning')
        if load['weight_t'] > truck['capacity_t']:
            issue('OVER_CAPACITY',f"Cargo weighs {load['weight_t']:g} t; truck capacity is {truck['capacity_t']:g} t")
        if load['truck_type'] != truck['type']:
            issue('TRUCK_TYPE_MISMATCH',f"Cargo requires {load['truck_type']}; truck is {truck['type']}")
    return dict(ok=not any(i['severity']=='error' for i in issues),issues=issues)


def check_plan(plan: dict, scenario: dict, config: dict) -> dict:
    trucks={t['id']:t for t in scenario['trucks']}
    loads={l['id']:l for l in scenario['loads']}
    return {f"{tp['truck_id']}#{leg['seq']}":check_leg(leg,loads.get(leg.get('load_id')),trucks[tp['truck_id']],config)
            for tp in plan['trucks'] for leg in tp['legs']}
