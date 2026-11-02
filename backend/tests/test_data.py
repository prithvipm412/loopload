import copy
import json
from pathlib import Path

import pytest

from app.config import CONFIG, elapsed_h
from data import distance, generator
from data.lanes import seasonal_lanes


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    real = generator.DATA
    (tmp_path/'cities.json').write_text((real/'cities.json').read_text())
    monkeypatch.setattr(generator,'DATA',tmp_path)
    return generator.generate_scenario()


def test_matrix():
    cities=json.loads((distance.DATA/'cities.json').read_text())
    matrix=distance.get_matrix(cities)
    assert len(cities)==25
    assert matrix['cities']==[c['id'] for c in cities]
    for field in ('distance_km','duration_h'):
        assert len(matrix[field])==25
        assert all(len(row)==25 for row in matrix[field])
        assert all(matrix[field][i][i]==0 for i in range(25))
        assert all(value>=0 for row in matrix[field] for value in row)


def test_scenario_contract(scenario):
    assert set(scenario)=={'week_start','cities','owners','trucks','loads'}
    assert len(scenario['owners'])==6 and len(scenario['trucks'])==20 and len(scenario['loads'])==140
    codes={c['id'] for c in scenario['cities']}
    regs={t['reg_no'] for t in scenario['trucks']}
    types={'open_body','container','reefer'}
    for owner in scenario['owners']:
        assert 2<=len(owner['trucks'])<=5
        assert owner['home_city'] in codes
        assert owner['trucks']==[t['id'] for t in scenario['trucks'] if t['owner_id']==owner['id']]
    for truck in scenario['trucks']:
        assert truck['type'] in types and truck['capacity_t'] in (9,16,21,25)
        assert truck['start_city'] in codes and truck['home_city'] in codes
        assert 0<=truck['available_from_h']<=24
        assert truck['driver']['language'] in ('ta','hi','kn','en')
    allowed={(l['origin'],l['destination'],l['commodity'],l['truck_type']) for l in seasonal_lanes()}
    for i,load in enumerate(scenario['loads']):
        assert load['origin'] in codes and load['destination'] in codes
        assert 0<=load['pickup_start_h']<load['pickup_end_h']<load['deliver_by_h']<=168
        assert 7.99<=load['pickup_end_h']-load['pickup_start_h']<=24.01
        assert load['freight_inr']%100==0
        assert load['source'] in ('broker','shipper')
        if i>=4:
            assert tuple(load[k] for k in ('origin','destination','commodity','truck_type')) in allowed
        if load['eway_bill']:
            assert load['eway_bill']['vehicle_reg'] in regs|{'MH00ZZ0000'}


def test_determinism(scenario):
    assert generator.generate_scenario()==scenario
    assert generator.generate_scenario(seed=43)!=scenario


def test_hero_loop(scenario):
    truck=scenario['trucks'][0]
    assert (truck['id'],truck['owner_id'],truck['home_city'],truck['start_city'],truck['type'],truck['capacity_t'],truck['available_from_h'])==('T01','O1','TPR','TPR','open_body',21,0)
    matrix=distance.get_matrix(scenario['cities']); idx={c:i for i,c in enumerate(matrix['cities'])}
    ready=0; city='TPR'
    expected=[('TPR','DEL','Textiles'),('DEL','JAI','FMCG'),('JAI','NAG','Marble'),('NAG','TPR','Oranges')]
    for load, route in zip(scenario['loads'][:4],expected):
        assert (load['origin'],load['destination'],load['commodity'])==route
        assert load['truck_type']=='open_body' and load['weight_t']<=21
        assert city==load['origin'] and ready<=load['pickup_end_h']
        arrive=max(ready,load['pickup_start_h'])+3+elapsed_h(matrix['duration_h'][idx[city]][idx[load['destination']]])
        assert arrive<=load['deliver_by_h']
        assert load['eway_bill']['valid_until_h']>=arrive
        for other in scenario['loads'][4:]:
            if other['origin']==load['destination'] and other['truck_type']=='open_body':
                assert not other['pickup_start_h']<=arrive<=other['pickup_end_h']
        ready=arrive+3; city=load['destination']
    assert ready<=168


def test_matrix_failure_and_offline_cache(tmp_path,monkeypatch):
    monkeypatch.setattr(distance,'DATA',tmp_path)
    calls=[]
    def fail(url):
        calls.append(url)
        raise OSError('offline')
    monkeypatch.setattr(distance,'_request',fail)
    cities=[dict(id='A',lon=77,lat=12),dict(id='B',lon=78,lat=13)]
    matrix=distance.get_matrix(cities)
    assert matrix['source']=='haversine'
    assert matrix['distance_km'][0][1]==round(distance._haversine(*cities),1)
    assert distance.get_matrix(cities)==matrix and len(calls)==1
    (tmp_path/'cities.json').write_text(json.dumps(cities))
    assert distance.get_path('A','B')==[[77,12],[78,13]]
    assert distance.get_path('A','B')==[[77,12],[78,13]] and len(calls)==2


def test_path_simplification_and_prefetch(tmp_path,monkeypatch):
    monkeypatch.setattr(distance,'DATA',tmp_path)
    (tmp_path/'cities.json').write_text(json.dumps([dict(id='A',lon=0,lat=0),dict(id='B',lon=99,lat=99)]))
    monkeypatch.setattr(distance,'_request',lambda url: {'routes':[{'geometry':{'coordinates':[[i,i] for i in range(100)]}}]})
    sleeps=[]
    monkeypatch.setattr(distance.time,'sleep',sleeps.append)
    distance.prefetch_paths([('A','B'),('A','B')])
    path=distance.get_path('A','B')
    assert len(path)==60 and path[0]==[0,0] and path[-1]==[99,99]
    assert sleeps==[.2]

