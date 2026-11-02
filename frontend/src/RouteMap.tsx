import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import {
  PathLayer,
  ScatterplotLayer,
  TextLayer,
  ArcLayer,
} from "@deck.gl/layers";
import { TripsLayer } from "@deck.gl/geo-layers";
import type { PathStyleExtensionProps } from "@deck.gl/extensions";
import { PathStyleExtension } from "@deck.gl/extensions";
import { Map } from "react-map-gl/maplibre";
import type { PickingInfo } from "@deck.gl/core";
import type { Scenario, Plan, Leg, Forecast } from "./types";
import { money, num } from "./format";
import "maplibre-gl/dist/maplibre-gl.css";
interface Props {
  scenario: Scenario;
  plan: Plan;
  previous?: Plan;
  blend: number;
  time: number;
  owner: string;
  changed: string[];
  onSelect: (id: string) => void;
  hot?: Forecast[];
  mini?: boolean;
}
export default function RouteMap({
  scenario,
  plan,
  previous,
  blend,
  time,
  owner,
  changed,
  onSelect,
  hot,
  mini,
}: Props) {
  const [hover, setHover] = useState<PickingInfo<Leg> | null>(null);
  const [mapFailed, setMapFailed] = useState(false);
  const city = (id: string) => scenario.cities.find((c) => c.id === id)!;
  const layers = useMemo(() => {
    const routeLayers = (p: Plan, opacity: number, suffix: string) =>
      ["loaded", "empty"].map(
        (kind) =>
          new PathLayer<Leg, PathStyleExtensionProps<Leg>>({
            id: `${suffix}-${kind}`,
            data: p.trucks
              .flatMap((t) => t.legs)
              .filter((l) => l.kind === kind),
            getPath: (l) => l.path,
            getColor: (l) =>
              [
                ...(kind === "loaded" ? [95, 166, 127] : [217, 105, 94]),
                owner &&
                scenario.trucks.find((t) => t.id === l.truck_id)?.owner_id !==
                  owner
                  ? 35
                  : 230,
              ] as [number, number, number, number],
            getWidth: (l) =>
              changed.includes(l.truck_id) || hover?.object === l ? 6 : 3.5,
            widthUnits: "pixels",
            opacity,
            pickable: true,
            onHover: (info) => setHover(info as PickingInfo<Leg>),
            onClick: (info) => info.object && onSelect(info.object.truck_id),
            extensions:
              kind === "empty" ? [new PathStyleExtension({ dash: true })] : [],
            getDashArray: [6, 4],
            dashJustified: true,
            updateTriggers: {
              getColor: [owner],
              getWidth: [hover?.object, changed],
            },
          }),
      );
    const positions = plan.trucks.flatMap((t) =>
      t.legs
        .filter((l) => time >= l.depart_h && time <= l.arrive_h)
        .map((l) => {
          const f =
            ((time - l.depart_h) / (l.arrive_h - l.depart_h)) *
            (l.path.length - 1);
          const i = Math.min(l.path.length - 2, Math.floor(f));
          const a = l.path[i],
            b = l.path[i + 1];
          return {
            truck_id: t.truck_id,
            position: [
              a[0] + (b[0] - a[0]) * (f - i),
              a[1] + (b[1] - a[1]) * (f - i),
            ],
          };
        }),
    );
    return [
      ...(previous ? routeLayers(previous, 1 - blend, "old") : []),
      ...routeLayers(plan, blend, "current"),
      new TripsLayer<Leg>({
        id: "trips",
        data: plan.trucks.flatMap((t) => t.legs),
        getPath: (l) => l.path,
        getTimestamps: (l) =>
          l.path.map(
            (_, i) =>
              l.depart_h +
              ((l.arrive_h - l.depart_h) * i) / (l.path.length - 1),
          ),
        getColor: [169, 155, 224],
        widthMinPixels: 5,
        trailLength: 6,
        currentTime: time,
        opacity: 0.95,
      }),
      new ScatterplotLayer({
        id: "cities",
        data: mini
          ? scenario.cities.filter((c) =>
              plan.trucks.some((t) =>
                t.legs.some((l) => l.from === c.id || l.to === c.id),
              ),
            )
          : scenario.cities,
        getPosition: (c) => [c.lon, c.lat],
        getRadius: mini ? 3 : 4,
        radiusUnits: "pixels",
        getFillColor: [250, 247, 242],
        getLineColor: [122, 112, 100],
        stroked: true,
        lineWidthMinPixels: 1.5,
        pickable: true,
      }),
      new TextLayer({
        id: "labels",
        data: mini
          ? scenario.cities.filter((c) =>
              plan.trucks.some((t) =>
                t.legs.some((l) => l.from === c.id || l.to === c.id),
              ),
            )
          : scenario.cities,
        getPosition: (c) => [c.lon, c.lat],
        getText: (c) => c.name,
        getSize: mini ? 10 : 11,
        getColor: [74, 66, 56],
        getPixelOffset: [0, 12],
        fontFamily: "Inter, sans-serif",
        getTextAnchor: "middle",
        outlineWidth: 3,
        outlineColor: [250, 247, 242, 230],
      }),
      new ScatterplotLayer({
        id: "trucks",
        data: positions,
        getPosition: (d) => d.position,
        getRadius: 7,
        radiusUnits: "pixels",
        getFillColor: [169, 155, 224],
        stroked: true,
        getLineColor: [255, 253, 249],
        lineWidthMinPixels: 2,
        pickable: true,
        onClick: (info) => info.object && onSelect(info.object.truck_id),
      }),
      ...(hot
        ? [
            new ArcLayer<Forecast>({
              id: "hot-lanes",
              data: hot,
              getSourcePosition: (f) => [
                city(f.origin).lon,
                city(f.origin).lat,
              ],
              getTargetPosition: (f) => [
                city(f.destination).lon,
                city(f.destination).lat,
              ],
              getSourceColor: [244, 177, 131],
              getTargetColor: [217, 137, 82],
              getWidth: (f) => Math.max(2, f.forecast[0].loads / 6),
              pickable: true,
            }),
          ]
        : []),
    ];
  }, [
    scenario,
    plan,
    previous,
    blend,
    time,
    owner,
    changed,
    hover?.object,
    hot,
    mini,
  ]);
  return (
    <div data-testid="map-canvas" className="map-canvas">
      <DeckGL
        initialViewState={{
          longitude: 79,
          latitude: 21,
          zoom: mini ? 2.1 : 3.4,
          pitch: 0,
          bearing: 0,
        }}
        controller
        layers={layers}
        getCursor={({ isHovering }) => (isHovering ? "pointer" : "grab")}
      >
        <Map
          mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
          attributionControl={false}
          onLoad={(e) => {
            if (mini) {
              for (const layer of e.target.getStyle().layers || []) {
                if (layer.type === "symbol")
                  e.target.setLayoutProperty(layer.id, "visibility", "none");
              }
            }
          }}
          onError={() => setMapFailed(true)}
        />
      </DeckGL>
      {mapFailed && (
        <div className="map-notice">
          Basemap unavailable · route overlay remains interactive
        </div>
      )}
      {hover?.object && (
        <div
          className="map-tooltip"
          style={{
            left: Math.min(hover.x + 16, 500),
            top: Math.max(20, hover.y - 80),
          }}
        >
          <strong>
            {city(hover.object.from)?.name} → {city(hover.object.to)?.name}
          </strong>
          <span>
            {hover.object.kind === "empty"
              ? "Empty return"
              : scenario.loads.find((l) => l.id === hover.object?.load_id)
                  ?.commodity || "Cargo"}{" "}
            · {hover.object.truck_id}
          </span>
          <span>
            {num(hover.object.distance_km)} km ·{" "}
            {money(hover.object.revenue_inr)}
          </span>
        </div>
      )}
    </div>
  );
}
