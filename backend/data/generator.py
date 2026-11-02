"""Deterministic seasonal freight scenario and explicitly authorised hero loop."""
import json
import math
import random
from collections import Counter
from pathlib import Path

from app.config import CONFIG, elapsed_h
from data.distance import get_matrix
from data.lanes import seasonal_lanes

DATA = Path(__file__).resolve().parent
HOMES = ['TPR','NSK','JAI','NAG','LDH','HYD']
NAMES = ['Sri Murugan Logistics','Balaji Roadways','Pink City Transport','Vidarbha Carriers','Punjab Freightways','Deccan Roadlines']
REGIONS = {
    'TPR': ('TN39','ta',['Murugan','Senthil','Kumar','Ravi','Selvam']),
    'NSK': ('MH15','hi',['Ganesh','Santosh','Prakash','Vijay','Sanjay']),
    'JAI': ('RJ14','hi',['Mahendra','Ramesh','Suresh','Mohan','Dinesh']),
    'NAG': ('MH31','hi',['Rajesh','Nitin','Ashok','Sunil','Deepak']),
    'LDH': ('PB10','hi',['Gurpreet','Harpreet','Baldev','Manpreet','Jaspreet']),
    'HYD': ('TS09','en',['Raju','Srinivas','Venkat','Naresh','Mahesh']),
}
VALUES = {'Onions': (400000,800000), 'Cotton bales': (1000000,2200000),
          'Textiles': (1500000,3000000), 'Oranges': (500000,1000000),
          'Marble': (800000,1800000), 'Machinery / auto parts': (2000000,5000000),
          'FMCG': (1200000,2800000), 'Steel': (700000,1800000),
          'Wheat': (400000,900000), 'Spices': (1500000,3500000),
          'Pharma': (4000000,8000000)}


def generate_scenario(seed: int = 42, n_trucks: int = 20, n_owners: int = 6, n_loads: int = 140) -> dict:
    """Write and return a reproducible week; first four loads form T01's loop."""
    if n_owners < 1 or not 2*n_owners <= n_trucks <= 5*n_owners:
        raise ValueError('Each owner must have 2–5 trucks')
    if n_loads < 4:
        raise ValueError('At least four loads are needed for the hero loop')
    rng = random.Random(seed)
    cities = json.loads((DATA/'cities.json').read_text())
    matrix = get_matrix(cities)
    index = {c: i for i,c in enumerate(matrix['cities'])}
    def km(a,b): return matrix['distance_km'][index[a]][index[b]]
    def travel(a,b): return elapsed_h(matrix['duration_h'][index[a]][index[b]])
    counts = [2]*n_owners
    for i in range(n_trucks-2*n_owners): counts[i % n_owners] += 1
    owners, trucks = [], []
    types = ['open_body']*round(n_trucks*.6) + ['container']*round(n_trucks*.3)
    types += ['reefer']*(n_trucks-len(types))
    rng.shuffle(types)
    # Preserve exact fleet mix while fixing the hero vehicle's equipment.
    open_index = types.index('open_body')
    types[0],types[open_index] = types[open_index],types[0]
    for oi,count in enumerate(counts):
        home = HOMES[oi % len(HOMES)]
        owner = dict(id=f'O{oi+1}',name=NAMES[oi % len(NAMES)],home_city=home,trucks=[])
        prefix,language,drivers = REGIONS[home]
        for j in range(count):
            ti = len(trucks); tid = f'T{ti+1:02d}'
            truck = dict(id=tid,owner_id=owner['id'],reg_no=f'{prefix}AB{1201+ti}',
                         type=types[ti],capacity_t=rng.choice([9,16,21,25]),home_city=home,
                         start_city=home if rng.random()<.8 else rng.choice(HOMES),
                         available_from_h=round(rng.uniform(0,24),1),
                         national_permit_valid_until='2027-03-31',
                         driver=dict(name=drivers[j % len(drivers)],language=language))
            if ti == 0: truck.update(capacity_t=21,start_city='TPR',available_from_h=0)
            trucks.append(truck); owner['trucks'].append(tid)
        owners.append(owner)
    # The hero loop (below) needs T01 to be the uniquely best-positioned open_body
    # truck for it: any other truck of the same type starting in the same city
    # is an equally cheap fit and the optimizer could assign the loop to either.
    # Swap such rivals to a different type, preserving the fleet-wide type mix.
    hero_type, hero_start = trucks[0]['type'], trucks[0]['start_city']
    rivals = [i for i,t in enumerate(trucks) if i and t['type']==hero_type and t['start_city']==hero_start]
    swap_pool = [i for i,t in enumerate(trucks) if i and t['type']!=hero_type and t['start_city']!=hero_start]
    for rival,other in zip(rivals,swap_pool):
        trucks[rival]['type'],trucks[other]['type'] = trucks[other]['type'],trucks[rival]['type']
    loads = []
    def make_load(lane, start, end, assigned=None):
        a,b,c,t = (lane[k] for k in ('origin','destination','commodity','truck_type'))
        lo,hi = VALUES[c]
        compatible = [x for x in trucks if x['type']==t]
        truck = assigned or (rng.choice(compatible) if compatible else trucks[0])
        return dict(id=f'L{len(loads)+1:03d}',origin=a,destination=b,commodity=c,
                    weight_t=round(rng.uniform(6,min(16,truck['capacity_t'])),1),truck_type=t,
                    pickup_start_h=round(start,2),pickup_end_h=round(end,2),
                    deliver_by_h=round(min(168,end+travel(a,b)+3+rng.uniform(12,36)),2),
                    freight_inr=int(round(km(a,b)*rng.uniform(38,55)/100)*100),
                    cargo_value_inr=int(round(rng.uniform(lo,hi)/1000)*1000),
                    source='broker' if rng.random()<.7 else 'shipper',
                    eway_bill=dict(number=f'EWB{1000000000+len(loads)+1}',
                                   valid_until_h=round(start+max(1,math.ceil(km(a,b)/200))*24,2),
                                   vehicle_reg=truck['reg_no']))
    ready = 0
    hero_arrivals = {}
    for a,b,c in [('TPR','DEL','Textiles'),('DEL','JAI','FMCG'),('JAI','NAG','Marble'),('NAG','TPR','Oranges')]:
        start = ready+2
        end = start+8
        load = make_load(dict(origin=a,destination=b,commodity=c,truck_type='open_body'), start,end,trucks[0])
        loads.append(load)
        arrival = start+CONFIG['load_unload_h']+travel(a,b)
        hero_arrivals[b] = arrival
        ready = arrival+CONFIG['load_unload_h']
    if ready > 168:
        raise ValueError(f'Hero loop needs {ready:.1f} hours with this matrix; cannot fit contract week')
    lanes = seasonal_lanes()
    weights = [dict(Onions=7,Oranges=7,**{'Cotton bales':5},FMCG=5).get(l['commodity'],1) for l in lanes]
    while len(loads)<n_loads:
        lane = rng.choices(lanes,weights=weights,k=1)[0]
        drive = travel(lane['origin'],lane['destination'])
        latest_end = min(156,168-drive-3-12)
        if latest_end < 9:
            raise ValueError('Lane cannot fit inside the planning horizon')
        width = rng.uniform(8,min(24,latest_end-1))
        start = rng.uniform(0,latest_end-width)
        if lane['truck_type']=='open_body' and lane['origin'] in hero_arrivals:
            arrival = hero_arrivals[lane['origin']]
            # End ordinary windows before T01 arrives, leaving only its future hero pickup.
            latest_end = min(latest_end, arrival-6)
            if latest_end < width:
                continue
            start = rng.uniform(0,latest_end-width)
        loads.append(make_load(lane,start,start+width))
    # Preserve the hero bills, and plant roughly 5% explicit demo defects.
    for i,li in enumerate(rng.sample(range(4,len(loads)),min(len(loads)-4,round(n_loads*.05)))):
        load=loads[li]
        if i%3==0: load['eway_bill']=None
        elif i%3==1: load['eway_bill']['valid_until_h']=load['pickup_start_h']+1
        else: load['eway_bill']['vehicle_reg']='MH00ZZ0000'
    scenario=dict(week_start=CONFIG['week_start'],cities=cities,owners=owners,trucks=trucks,loads=loads)
    (DATA/'scenario.json').write_text(json.dumps(scenario,indent=2)+'\n')
    return scenario


if __name__ == '__main__':
    scenario=generate_scenario()
    print(dict(Counter(l['commodity'] for l in scenario['loads'])))
