"""Synthetic seasonal history and cached additive Holt-Winters forecasts."""
import json
import math
import random
import warnings
from datetime import date, timedelta
from pathlib import Path

from data.lanes import seasonal_lanes

DATA=Path(__file__).resolve().parent
WEEK_START=date(2026,11,9)


def _lanes():
    lanes=seasonal_lanes()
    counts={}
    for lane in lanes:
        od=f"{lane['origin']}-{lane['destination']}"
        counts[od]=counts.get(od,0)+1
    suffix={'Onions':'ONI','Cotton bales':'COT','Textiles':'TEX','Oranges':'ORA',
            'Marble':'MAR','Machinery / auto parts':'MAC','FMCG':'FMC','Steel':'STE',
            'Wheat':'WHE','Spices':'SPI','Pharma':'PHA'}
    for lane in lanes:
        od=f"{lane['origin']}-{lane['destination']}"
        lane['lane']=od if counts[od]==1 else f"{od}-{suffix[lane['commodity']]}"
    return lanes


def _save(name,value):
    path=DATA/name
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n')
    temporary.replace(path)


def build_history(seed: int = 42) -> dict[str,list[dict]]:
    rng=random.Random(seed)
    history={}
    for lane in _lanes():
        commodity=lane['commodity']
        base=rng.uniform(15,20) if commodity in ('Onions','Oranges') else rng.uniform(3,12)
        amplitude=rng.uniform(1.1,1.7)
        trend=rng.uniform(.002,.015)
        rows=[]
        for i in range(104):
            week=WEEK_START-timedelta(weeks=104-i)
            month=week.month+(week.day-1)/30.44
            if lane['peaks']:
                # Smooth yearly bumps centred on each peak month.
                bumps=[]
                for peak in lane['peaks']:
                    delta=abs(month-(peak+.5)); delta=min(delta,12-delta)
                    bumps.append(max(0,math.cos(math.pi*delta/3)))
                season=max(bumps)
                mean=base*(.65+amplitude*season)
            else:
                mean=base*(1+.1*math.cos(2*math.pi*i/52))
            mean += trend*i
            count=max(0,round(mean+rng.gauss(0,math.sqrt(mean)*.6)))
            rows.append(dict(week=week.isoformat(),loads=count))
        history[lane['lane']]=rows
    _save('history.json',history)
    # Forecast cache is valid only for precisely this generated history.
    (DATA/'forecast.json').unlink(missing_ok=True)
    return history


def forecast_lanes(weeks_ahead: int = 4) -> list[dict]:
    if weeks_ahead<1:
        raise ValueError('weeks_ahead must be positive')
    try:
        history=json.loads((DATA/'history.json').read_text())
    except (OSError,ValueError):
        history=build_history()
    try:
        cached=json.loads((DATA/'forecast.json').read_text())
        if len(cached)==len(history) and all(
            len(f['forecast'])==weeks_ahead and f['history']==history.get(f['lane']) for f in cached
        ):
            return cached
    except (OSError,ValueError,KeyError,TypeError):
        pass
    forecasts=[]
    for lane in _lanes():
        rows=history[lane['lane']]
        values=[float(r['loads']) for r in rows]
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                model=ExponentialSmoothing(values,trend='add',seasonal='add',seasonal_periods=52).fit()
            prediction=list(model.forecast(weeks_ahead))
            residual=list(model.resid)
            if not all(math.isfinite(float(v)) for v in prediction+residual):
                raise ValueError('Nonfinite fit')
        except Exception:
            prediction=[values[len(values)-52+i%52] for i in range(weeks_ahead)]
            residual=[values[i]-values[i-52] for i in range(52,len(values))]
        residual_mean=sum(residual)/len(residual)
        std=math.sqrt(sum((r-residual_mean)**2 for r in residual)/max(1,len(residual)-1))
        band=1.96*std
        points=[]
        for i,value in enumerate(prediction):
            point=max(0,float(value))
            points.append(dict(week=(WEEK_START+timedelta(weeks=i)).isoformat(),loads=round(point,1),
                               lower=round(max(0,point-band),1),upper=round(point+band,1)))
        recent=sum(values[-4:])/4
        change=(points[0]['loads']/recent-1)*100 if recent else 0
        forecasts.append(dict(lane=lane['lane'],origin=lane['origin'],destination=lane['destination'],
                              commodity=lane['commodity'],history=rows,forecast=points,change_pct=round(change,1)))
    _save('forecast.json',forecasts)
    return forecasts


def hot_lanes(n: int = 8) -> list[dict]:
    return sorted(forecast_lanes(),key=lambda f:(-f['forecast'][0]['loads'],-f['change_pct'],f['lane']))[:max(0,n)]


def forecast_loads(week_start_h: float = 168) -> list[dict]:
    """Twelve optional next-week loads; probability is a demo assumption.

    These are demand projections, separate from the committed current-week
    scenario. IDs and all generated fields are deterministic for a given cache.
    """
    from app.config import elapsed_h
    from data.distance import DATA as CITY_DATA, get_matrix
    from data.generator import VALUES
    if week_start_h<0:
        raise ValueError('week_start_h must be nonnegative')
    cities=json.loads((CITY_DATA/'cities.json').read_text())
    scenario=json.loads((CITY_DATA/'scenario.json').read_text())
    matrix=get_matrix(cities)
    index={c:i for i,c in enumerate(matrix['cities'])}
    lanes={l['lane']:l for l in _lanes()}
    rng=random.Random(42)
    loads=[]
    for forecast in hot_lanes(6):
        lane=lanes[forecast['lane']]
        a,b=lane['origin'],lane['destination']
        distance=matrix['distance_km'][index[a]][index[b]]
        travel=elapsed_h(matrix['duration_h'][index[a]][index[b]])
        point=forecast['forecast'][0]
        probability=round(max(.55,min(.95,1-(point['upper']-point['lower'])/(4*max(1,point['loads'])))),2)
        candidates=[t for t in scenario['trucks'] if t['type']==lane['truck_type']]
        reg=candidates[0]['reg_no'] if candidates else scenario['trucks'][0]['reg_no']
        for offset in (8,48):
            start=week_start_h+offset
            end=start+12
            low,high=VALUES[lane['commodity']]
            li=len(loads)+1
            loads.append(dict(id=f'F{li:03d}',origin=a,destination=b,commodity=lane['commodity'],
                              weight_t=round(rng.uniform(6,9),1),truck_type=lane['truck_type'],
                              pickup_start_h=start,pickup_end_h=end,
                              deliver_by_h=round(min(week_start_h+168,end+travel+3+24),2),
                              freight_inr=int(round(distance*rng.uniform(38,55)/100)*100),
                              cargo_value_inr=int(round(rng.uniform(low,high)/1000)*1000),
                              source='broker',probability=probability,
                              eway_bill=dict(number=f'EWB{2000000000+li}',
                                             valid_until_h=start+max(1,math.ceil(distance/200))*24,
                                             vehicle_reg=reg)))
    return loads
