import copy
import csv
import json
from pathlib import Path

import pytest

from data.importer import BILL_FIELDS, FIELDS, CSVImportError, import_loads_csv

DATA=Path(__file__).resolve().parents[1]/'data'


@pytest.fixture
def scenario():
    return json.loads((DATA/'scenario.json').read_text())


def write_rows(tmp_path, rows, fields=FIELDS+BILL_FIELDS):
    path=tmp_path/'loads.csv'
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader();writer.writerows(rows)
    return path


def sample():
    with (DATA/'sample_loads.csv').open() as f:
        return list(csv.DictReader(f))


def test_sample_contract_and_no_mutation(scenario):
    before=copy.deepcopy(scenario)
    loads=import_loads_csv(DATA/'sample_loads.csv',scenario)
    assert len(loads)==15 and scenario==before
    assert loads==import_loads_csv(DATA/'sample_loads.csv',scenario)
    for load in loads:
        assert set(load)==set(FIELDS)|{'eway_bill'}
        assert set(load['eway_bill'])=={'number','valid_until_h','vehicle_reg'}
        assert isinstance(load['freight_inr'],int) and isinstance(load['cargo_value_inr'],int)
        assert 0<=load['pickup_start_h']<load['pickup_end_h']<load['deliver_by_h']<=168


@pytest.mark.parametrize('field,value',[
    ('origin','XXX'),('destination','XXX'),('truck_type','flatbed'),
    ('pickup_start_h','-1'),('pickup_end_h','168'),('deliver_by_h','169'),
    ('weight_t','0'),('weight_t','nan'),('freight_inr','12.5'),
    ('cargo_value_inr','-1'),('source','unknown'),('commodity',''),
    ('id','L001'),('eway_bill_valid_until_h','inf')])
def test_row_errors(tmp_path,scenario,field,value):
    rows=sample()[:1];rows[0][field]=value
    with pytest.raises(CSVImportError) as exc:
        import_loads_csv(write_rows(tmp_path,rows),scenario)
    assert any(e['row']==2 for e in exc.value.errors)
    assert 'Row 2' in str(exc.value)


def test_accumulates_all_rows_and_duplicate_ids(tmp_path,scenario):
    rows=sample()[:2];rows[0]['origin']='XXX';rows[1]['id']=rows[0]['id']
    with pytest.raises(CSVImportError) as exc:
        import_loads_csv(write_rows(tmp_path,rows),scenario)
    assert {e['row'] for e in exc.value.errors}=={2,3}


def test_missing_bill_is_null_partial_bill_is_error(tmp_path,scenario):
    rows=sample()[:1]
    for key in BILL_FIELDS:rows[0][key]=''
    assert import_loads_csv(write_rows(tmp_path,rows),scenario)[0]['eway_bill'] is None
    rows[0]['eway_bill_number']='EWB123'
    with pytest.raises(CSVImportError,match='all three'):
        import_loads_csv(write_rows(tmp_path,rows),scenario)


def test_header_and_empty_file(tmp_path,scenario):
    path=tmp_path/'bad.csv';path.write_text('origin\nNSK\n')
    with pytest.raises(CSVImportError,match='required column'):
        import_loads_csv(path,scenario)
    with pytest.raises(CSVImportError,match='contains no loads'):
        import_loads_csv(write_rows(tmp_path,[]),scenario)


def test_ragged_row(tmp_path,scenario):
    path=write_rows(tmp_path,sample()[:1]);path.write_text(path.read_text()+',extra\n')
    with pytest.raises(CSVImportError,match='column count'):
        import_loads_csv(path,scenario)
