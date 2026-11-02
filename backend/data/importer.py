"""Import broker CSVs without changing the scenario.

Columns are the Load scalar fields plus optional eway_bill_number,
eway_bill_valid_until_h, eway_bill_vehicle_reg. Leave all three bill cells blank
for eway_bill=null (compliance checks decide whether a bill is required).
All rows are validated before returning. CSVImportError.errors contains
{row, field, message} records; row 1 is the header, row 2 the first load.
No partial imports are returned and the input scenario is never mutated.
"""
import csv
import math
import re
from pathlib import Path

FIELDS = ('id','origin','destination','commodity','weight_t','truck_type',
          'pickup_start_h','pickup_end_h','deliver_by_h','freight_inr','cargo_value_inr','source')
BILL_FIELDS = ('eway_bill_number','eway_bill_valid_until_h','eway_bill_vehicle_reg')


class CSVImportError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__('CSV import failed:\n' + '\n'.join(
            f"Row {e['row']}, {e['field']}: {e['message']}" for e in errors))


def import_loads_csv(path, scenario) -> list[dict]:
    cities = {city['id'] for city in scenario['cities']}
    seen = {load['id'] for load in scenario.get('loads', [])}
    errors, loads = [], []
    def error(row, field, message):
        errors.append(dict(row=row,field=field,message=message))
    try:
        stream = Path(path).open(newline='',encoding='utf-8-sig')
    except OSError as exc:
        raise CSVImportError([dict(row=1,field='file',message=str(exc))]) from exc
    with stream:
        reader = csv.DictReader(stream, strict=True)
        try:
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)):
                error(1,'header','duplicate column names')
            for field in FIELDS:
                if field not in headers:
                    error(1,field,'required column is missing')
            for field in headers:
                if field not in FIELDS + BILL_FIELDS:
                    error(1,field,'unknown column')
            if errors:
                raise CSVImportError(errors)
            for raw in reader:
                row = reader.line_num
                before = len(errors)
                if None in raw or any(value is None for value in raw.values()):
                    error(row,'row','column count does not match header')
                    continue
                data = {key:value.strip() for key,value in raw.items()}
                load = {key:data[key] for key in FIELDS}
                for field in FIELDS:
                    if not data[field]:
                        error(row,field,'value is required')
                lid = data['id']
                if not re.fullmatch(r'L\d{3,}',lid):
                    error(row,'id','use a load ID such as L141')
                if lid in seen:
                    error(row,'id',f'{lid} already exists in this scenario or CSV')
                seen.add(lid)
                for field in ('origin','destination'):
                    if data[field] not in cities:
                        error(row,field,f"unknown city code {data[field]!r}")
                if data['origin'] == data['destination']:
                    error(row,'destination','must differ from origin')
                if data['truck_type'] not in ('open_body','container','reefer'):
                    error(row,'truck_type','must be open_body, container, or reefer')
                if data['source'] not in ('broker','shipper'):
                    error(row,'source','must be broker or shipper')
                for field in ('weight_t','pickup_start_h','pickup_end_h','deliver_by_h'):
                    try:
                        value = float(data[field])
                        if not math.isfinite(value):
                            raise ValueError()
                        load[field] = value
                    except ValueError:
                        error(row,field,'must be a finite number')
                for field in ('freight_inr','cargo_value_inr'):
                    try:
                        load[field] = int(data[field])
                        if load[field] < 0:
                            raise ValueError()
                    except ValueError:
                        error(row,field,'must be a nonnegative whole number of rupees')
                if isinstance(load['weight_t'],float) and load['weight_t'] <= 0:
                    error(row,'weight_t','must be greater than zero')
                times = [load[k] for k in ('pickup_start_h','pickup_end_h','deliver_by_h')]
                if all(isinstance(v,float) and math.isfinite(v) for v in times):
                    if not 0 <= times[0] < times[1] < times[2] <= 168:
                        error(row,'windows','require 0 <= pickup_start_h < pickup_end_h < deliver_by_h <= 168')
                bill = [data.get(key,'') for key in BILL_FIELDS]
                load['eway_bill'] = None
                if any(bill):
                    if not all(bill):
                        error(row,'eway_bill','provide all three e-way bill fields or leave all blank')
                    else:
                        try:
                            until = float(bill[1])
                            if not math.isfinite(until) or until < 0:
                                raise ValueError()
                            load['eway_bill'] = dict(number=bill[0],valid_until_h=until,vehicle_reg=bill[2])
                        except ValueError:
                            error(row,'eway_bill_valid_until_h','must be a finite nonnegative hour')
                if len(errors) == before:
                    loads.append(load)
        except (csv.Error,UnicodeError) as exc:
            error(max(1,reader.line_num),'CSV',str(exc))
    if errors:
        raise CSVImportError(errors)
    if not loads:
        raise CSVImportError([dict(row=2,field='row',message='CSV contains no loads')])
    return loads
