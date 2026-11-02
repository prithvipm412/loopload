from copy import deepcopy

import pytest

from app.config import CONFIG
from engine.compliance import check_leg, check_plan


@pytest.fixture
def inputs():
    return (dict(kind='loaded',arrive_h=40,seq=0,truck_id='T01',load_id='L001'),
            dict(id='L001',cargo_value_inr=100000,weight_t=12,truck_type='open_body',
                 eway_bill=dict(valid_until_h=48,vehicle_reg='TN39AB1234')),
            dict(id='T01',reg_no='TN39AB1234',type='open_body',capacity_t=16,national_permit_valid_until='2027-03-31'))


@pytest.mark.parametrize('code', ['EWAY_MISSING','EWAY_EXPIRES','EWAY_VEHICLE_MISMATCH','OVER_CAPACITY','TRUCK_TYPE_MISMATCH','PERMIT_EXPIRED'])
def test_issue_codes(inputs,code):
    leg,load,truck=deepcopy(inputs)
    if code=='EWAY_MISSING': load['eway_bill']=None
    if code=='EWAY_EXPIRES': load['eway_bill']['valid_until_h']=39
    if code=='EWAY_VEHICLE_MISMATCH': load['eway_bill']['vehicle_reg']='OTHER'
    if code=='OVER_CAPACITY': load['weight_t']=17
    if code=='TRUCK_TYPE_MISMATCH': load['truck_type']='reefer'
    if code=='PERMIT_EXPIRED': truck['national_permit_valid_until']='2026-11-08'
    result=check_leg(leg,load,truck,CONFIG)
    assert [i['code'] for i in result['issues']]==[code]
    assert result['ok']==(code=='EWAY_VEHICLE_MISMATCH')
    assert result['issues'][0]['severity']==('warning' if result['ok'] else 'error')


def test_valid_boundaries(inputs):
    leg,load,truck=inputs
    load['eway_bill']['valid_until_h']=leg['arrive_h']
    load['weight_t']=truck['capacity_t']
    truck['national_permit_valid_until']='2026-11-09'
    assert check_leg(leg,load,truck,CONFIG)==dict(ok=True,issues=[])
    load.update(cargo_value_inr=50000,eway_bill=None)
    assert check_leg(leg,load,truck,CONFIG)['ok']


def test_empty_only_checks_permit(inputs):
    leg,load,truck=inputs
    leg['kind']='empty'; load.update(weight_t=100,truck_type='reefer',eway_bill=None)
    assert check_leg(leg,load,truck,CONFIG)==dict(ok=True,issues=[])
    truck['national_permit_valid_until']='2026-11-08'
    result=check_leg(leg,None,truck,CONFIG)
    assert [i['code'] for i in result['issues']]==['PERMIT_EXPIRED']


def test_check_plan_keys(inputs):
    leg,load,truck=inputs
    scenario=dict(trucks=[truck],loads=[load])
    plan=dict(trucks=[dict(truck_id='T01',legs=[leg])])
    assert check_plan(plan,scenario,CONFIG)=={'T01#0':dict(ok=True,issues=[])}
