export type Mode = 'baseline' | 'ai' | 'ai_solo';
export interface City {id:string;name:string;state:string;lat:number;lon:number}
export interface Owner {id:string;name:string;home_city:string;trucks:string[]}
export interface Truck {id:string;owner_id:string;reg_no:string;type:'open_body'|'container'|'reefer';capacity_t:number;home_city:string;start_city:string;available_from_h:number;national_permit_valid_until:string;driver:{name:string;language:'en'|'hi'|'kn'|'ta'}}
export interface Load {id:string;origin:string;destination:string;commodity:string;weight_t:number;truck_type:Truck['type'];pickup_start_h:number;pickup_end_h:number;deliver_by_h:number;freight_inr:number;cargo_value_inr:number;source:'broker'|'shipper';eway_bill:{number:string;valid_until_h:number;vehicle_reg:string}|null}
export interface ComplianceResult {ok:boolean;issues:{code:'EWAY_MISSING'|'EWAY_EXPIRES'|'EWAY_VEHICLE_MISMATCH'|'OVER_CAPACITY'|'TRUCK_TYPE_MISMATCH'|'PERMIT_EXPIRED';severity:'error'|'warning';message:string}[]}
export interface Leg {truck_id:string;seq:number;kind:'loaded'|'empty';from:string;to:string;load_id:string|null;depart_h:number;arrive_h:number;distance_km:number;revenue_inr:number;diesel_inr:number;toll_inr:number;co2_kg:number;path:[number,number][];compliance?:ComplianceResult}
export interface Metrics {total_km:number;loaded_km:number;empty_km:number;empty_pct:number;revenue_inr:number;diesel_inr:number;toll_inr:number;profit_inr:number;co2_kg:number;loads_served:number;loads_total:number;trucks_used:number;idle_h:number}
export interface TruckPlan {truck_id:string;legs:Leg[];totals:Metrics}
export interface Plan {plan_id:string;mode:Mode;created_at:string;solve_time_s:number;trucks:TruckPlan[];unassigned_loads:string[];metrics:Metrics}
export interface Scenario {week_start:string;cities:City[];owners:Owner[];trucks:Truck[];loads:Load[]}
export interface Compare {baseline:Metrics;ai:Metrics;delta:{empty_km:number;empty_pct:number;profit_inr:number;co2_kg:number;loads_served:number}}
export interface Forecast {lane:string;origin:string;destination:string;commodity:string;history:{week:string;loads:number}[];forecast:{week:string;loads:number;lower:number;upper:number}[];change_pct:number}
export type ReplanEvent = {type:'cancel_load';load_id:string;at_h:number}|{type:'delay_truck';truck_id:string;delay_h:number;at_h:number}|{type:'new_load';load:Load;at_h:number};
