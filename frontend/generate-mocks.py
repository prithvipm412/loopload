import json,math,re,pathlib
root=pathlib.Path(__file__).parent
text=(root.parent/'docs/CONTRACT.md').read_text()
cities=[dict(id=a,name=b,state=c,lat=float(d),lon=float(e)) for a,b,c,d,e in re.findall(r'\| ([A-Z]{3}) \| ([^|]+) \| ([^|]+) \| ([\d.]+) \| ([\d.]+) \|',text)]
cities=[{k:v.strip() if isinstance(v,str) else v for k,v in c.items()} for c in cities]; lookup={c['id']:c for c in cities}
owners=[dict(id=f'O{i+1}',name=n,home_city=h,trucks=[]) for i,(n,h) in enumerate([('Raju Transport','TPR'),('Deccan Logistics','BLR'),('Northern Freight','DEL'),('Western Carriers','AMD')])]
routes=[['TPR','DEL','JAI','NAG','TPR'],['BLR','HYD','NAG','CHE','BLR'],['MUM','AMD','JAI','PUN','MUM'],['NSK','DEL','KNP','IDR','NSK'],['RJK','TPR','CBE','AMD','RJK'],['CHE','VGA','VTZ','HYD','CHE'],['KOL','RPR','NAG','LKO','KOL'],['LDH','DEL','BPL','JAI','LDH'],['COK','BLR','MDU','CBE','COK'],['SRT','MUM','PUN','AMD','SRT']]
trucks=[];loads=[];plans={}
for i,r in enumerate(routes):
 o=owners[i%4];tid=f'T{i+1:02}';o['trucks'].append(tid)
 trucks.append(dict(id=tid,owner_id=o['id'],reg_no=f'TN39AB{1234+i}',type='container',capacity_t=16,home_city=r[0],start_city=r[0],available_from_h=0,national_permit_valid_until='2027-03-31',driver=dict(name=['Murugan','Ravi','Arjun','Kumar','Selvam'][i%5],language='ta')))
def metrics(legs):
 total=sum(l['distance_km'] for l in legs);empty=sum(l['distance_km'] for l in legs if l['kind']=='empty');rev=sum(l['revenue_inr'] for l in legs);diesel=sum(l['diesel_inr'] for l in legs);toll=sum(l['toll_inr'] for l in legs)
 return dict(total_km=round(total,1),loaded_km=round(total-empty,1),empty_km=round(empty,1),empty_pct=round(100*empty/total,1),revenue_inr=rev,diesel_inr=diesel,toll_inr=toll,profit_inr=rev-diesel-toll,co2_kg=round(sum(l['co2_kg'] for l in legs),1),loads_served=sum(l['kind']=='loaded' for l in legs),loads_total=40,trucks_used=1,idle_h=round(168-max(l['arrive_h'] for l in legs),1))
for mode in ['baseline','ai']:
 tps=[]
 for i,r in enumerate(routes):
  legs=[]; t=3.
  for j,(a,b) in enumerate(zip(r,r[1:])):
   x,y=lookup[a],lookup[b];dist=round(math.hypot((x['lon']-y['lon'])*100,(x['lat']-y['lat'])*111)*1.18,1)
   empty=((j==3 or (j==2 and i in [0,2,4])) if mode=='baseline' else (j==3 and i in [0,1,3,5,7,9]))
   dist=round(dist*(1.12 if mode=='baseline' else 1),1)
   lid=f'L{i*4+j+1:03}';commodity=['Textiles','FMCG','Marble','Oranges'][j];duration=dist/60
   # Demo routes include scheduled driver rest, within the week horizon.
   duration+=int(duration/10)*7
   end=t+duration
   issue=i in [0,3] and j==2
   leg=dict(truck_id=trucks[i]['id'],seq=j,kind='empty' if empty else 'loaded',from_=a,to=b,load_id=None if empty else lid,depart_h=round(t,1),arrive_h=round(end,1),distance_km=dist,revenue_inr=0 if empty else round(dist*53),diesel_inr=round(dist*22.5),toll_inr=round(dist*5),co2_kg=round(dist/4*2.68,1),path=[[x['lon'],x['lat']],[(x['lon']+y['lon'])/2+.18,(x['lat']+y['lat'])/2],[y['lon'],y['lat']]],compliance=dict(ok=not issue,issues=[dict(code='EWAY_EXPIRES',severity='error',message=f'E-way bill expires at {round(end-5)}h but delivery is planned at {round(end)}h')] if issue else []))
   leg['from']=leg.pop('from_');legs.append(leg)
   if mode=='ai':loads.append(dict(id=lid,origin=a,destination=b,commodity=commodity,weight_t=12,truck_type='container',pickup_start_h=round(t-1,1),pickup_end_h=round(t+3,1),deliver_by_h=round(end+4,1),freight_inr=round(dist*53),cargo_value_inr=1800000,source='broker',eway_bill=dict(number=f'EWB123456{len(loads):04}',valid_until_h=round(end-5 if issue else end+24,1),vehicle_reg=trucks[i]['reg_no'])))
   t=end+3
  tps.append(dict(truck_id=trucks[i]['id'],legs=legs,totals=metrics(legs)))
 m=metrics([l for t in tps for l in t['legs']]);m['trucks_used']=10;m['idle_h']=sum(t['totals']['idle_h'] for t in tps)
 plans[mode]=dict(plan_id=f'{mode}-demo0042',mode=mode,created_at='2026-11-02T22:40:00+05:30',solve_time_s=8.2 if mode=='ai' else .2,trucks=tps,unassigned_loads=[l['id'] for l in loads if not any(l['id']==x['load_id'] for t in tps for x in t['legs'])],metrics=m)
for p in plans.values():
 p['unassigned_loads']=[l['id'] for l in loads if not any(l['id']==x['load_id'] for t in p['trucks'] for x in t['legs'])]
trucks[0]['type']='open_body'
trucks[0]['capacity_t']=21
for l in loads[:4]: l['truck_type']='open_body'
scenario=dict(week_start='2026-11-09T00:00:00+05:30',cities=cities,owners=owners,trucks=trucks,loads=loads)
for name,data in [('scenario',scenario),('plan_baseline',plans['baseline']),('plan_ai',plans['ai']),('compare',dict(baseline=plans['baseline']['metrics'],ai=plans['ai']['metrics'],delta={k:round(plans['ai']['metrics'][k]-plans['baseline']['metrics'][k],1) for k in ['empty_km','empty_pct','profit_inr','co2_kg','loads_served']}))]:
 (root/'src/mocks'/f'{name}.json').write_text(json.dumps(data,indent=2))
# P1 fixtures remain deterministic and use the same metrics calculation as P0.
import copy,datetime
solo=copy.deepcopy(plans['ai']);solo['mode']='ai_solo';solo['plan_id']='ai-solo0042'
for i,tp in enumerate(solo['trucks']):
 for l in tp['legs']:
  if i>0 and (l['seq']==3 or (i in [1,3,5] and l['seq']==1)):
   l.update(kind='empty',load_id=None,revenue_inr=0,compliance=dict(ok=True,issues=[]))
 tp['totals']=metrics(tp['legs'])
solo['metrics']=metrics([l for t in solo['trucks'] for l in t['legs']]);solo['metrics']['trucks_used']=10;solo['metrics']['idle_h']=round(sum(t['totals']['idle_h'] for t in solo['trucks']),1)
solo['unassigned_loads']=[l['id'] for l in loads if not any(l['id']==x['load_id'] for t in solo['trucks'] for x in t['legs'])]
(root/'src/mocks/plan_solo.json').write_text(json.dumps(solo,indent=2))
forecasts=[]
for i,l in enumerate(loads[:8]):
 history=[dict(week=(datetime.date(2026,8,17)+datetime.timedelta(weeks=j)).isoformat(),loads=round(12+i+math.sin(j)*3+j*.6)) for j in range(12)]
 future=[dict(week=(datetime.date(2026,11,9)+datetime.timedelta(weeks=j)).isoformat(),loads=28-i+j*2,lower=23-i+j*2,upper=33-i+j*2) for j in range(4)]
 origin,destination,commodity=('NSK','DEL','Onions') if i==0 else (l['origin'],l['destination'],l['commodity'])
 forecasts.append(dict(lane=f'{origin}-{destination}',origin=origin,destination=destination,commodity=commodity,history=history,forecast=future,change_pct=31.5-i*2))
(root/'src/mocks/forecast.json').write_text(json.dumps(forecasts,indent=2))
