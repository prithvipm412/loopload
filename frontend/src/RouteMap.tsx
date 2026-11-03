import { useEffect, useMemo, useRef, useState } from "react";
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
import { Map, type MapRef } from "react-map-gl/maplibre";
import {
  WebMercatorViewport,
  type MapViewState,
  type PickingInfo,
} from "@deck.gl/core";
import type { Scenario, Plan, Leg, Forecast, City } from "./types";
import { money, num, explanation } from "./format";
import "maplibre-gl/dist/maplibre-gl.css";
import { Sparkles } from "lucide-react";
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
const INDIA_BOUNDS: [[number, number], [number, number]] = [
  [68, 6],
  [92, 36],
];
const MAX_BOUNDS: [[number, number], [number, number]] = [
  [60, 2],
  [100, 38],
];
type LegGroups = { loaded: Leg[]; empty: Leg[] };
type TruckPosition = { truck_id: string; position: [number, number] };
function splitLegs(legs: Leg[]): LegGroups {
  return {
    loaded: legs.filter((l) => l.kind === "loaded"),
    empty: legs.filter((l) => l.kind === "empty"),
  };
}
function truckPositions(legs: Leg[], time: number): TruckPosition[] {
  return legs
    .filter(
      (l) =>
        l.path.length >= 2 &&
        l.arrive_h > l.depart_h &&
        time >= l.depart_h &&
        time <= l.arrive_h,
    )
    .map((l) => {
      const f =
        ((time - l.depart_h) / (l.arrive_h - l.depart_h)) * (l.path.length - 1);
      const i = Math.min(l.path.length - 2, Math.floor(f));
      const a = l.path[i],
        b = l.path[i + 1];
      return {
        truck_id: l.truck_id,
        position: [
          a[0] + (b[0] - a[0]) * (f - i),
          a[1] + (b[1] - a[1]) * (f - i),
        ],
      };
    });
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
  const [mapReady, setMapReady] = useState(false);
  const mapRoot = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapRef>(null);
  const [initialZoom, setInitialZoom] = useState(mini ? 1.7 : 3);
  const [basemapLabelCount, setBasemapLabelCount] = useState<number>();
  const [size, setSize] = useState({ width: 800, height: 360 });
  const [viewState, setViewState] = useState<MapViewState>({
    longitude: 80,
    latitude: 22,
    zoom: mini ? 1.7 : 3,
    minZoom: mini ? 1.7 : 3,
    maxZoom: 7,
    pitch: 0,
    bearing: 0,
  });
  useEffect(() => {
    let frame = 0;
    const resize = () => {
      const bounds = mapRoot.current?.getBoundingClientRect();
      if (bounds?.width && bounds.height)
        setSize({ width: bounds.width, height: bounds.height });
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => mapRef.current?.getMap().resize());
    };
    const observer = new ResizeObserver(resize);
    if (mapRoot.current) observer.observe(mapRoot.current);
    window.addEventListener("resize", resize);
    resize();
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(frame);
    };
  }, []);
  useEffect(() => {
    if (!size.width || !size.height) return;
    const fit = new WebMercatorViewport(size).fitBounds(INDIA_BOUNDS, {
      padding: mini ? 8 : 16,
    });
    setInitialZoom(fit.zoom);
    setViewState({
      longitude: 80,
      latitude: 22,
      zoom: fit.zoom,
      minZoom: fit.zoom,
      maxZoom: 7,
      pitch: 0,
      bearing: 0,
    });
    const frame = requestAnimationFrame(() =>
      mapRef.current?.getMap().resize(),
    );
    return () => cancelAnimationFrame(frame);
  }, [size, mini]);
  const constrainView = (next: MapViewState): MapViewState => ({
    ...next,
    // One controlled camera keeps MapLibre and deck.gl aligned at every zoom.
    longitude: Math.max(
      MAX_BOUNDS[0][0],
      Math.min(MAX_BOUNDS[1][0], next.longitude),
    ),
    latitude: Math.max(
      MAX_BOUNDS[0][1],
      Math.min(MAX_BOUNDS[1][1], next.latitude),
    ),
    zoom: Math.max(initialZoom, Math.min(7, next.zoom)),
    minZoom: initialZoom,
    maxZoom: 7,
    pitch: 0,
    bearing: 0,
  });
  // Cull only overlapping labels in screen space; keep every city dot available.
  // This also works with software WebGL and does not alter basemap rendering.
  const labelCities = useMemo(() => {
    const viewport = new WebMercatorViewport({ ...viewState, ...size });
    const occupied: {
      left: number;
      right: number;
      top: number;
      bottom: number;
    }[] = [];
    const priority = (c: City) =>
      ["TPR", "DEL", "JAI", "NAG"].includes(c.id) ? 100 : 0;
    const candidates = scenario.cities.filter(
      (c) =>
        !mini ||
        plan.trucks.some((t) =>
          t.legs.some((l) => l.from === c.id || l.to === c.id),
        ),
    );
    // Truck-in-motion markers are drawn above labels, but a label text box
    // sitting under a moving truck is still illegible, so keep labels clear
    // of wherever trucks currently are, not just of each other.
    const truckPad = 10;
    const truckScreen = [
      ...truckPositions(plan.trucks.flatMap((t) => t.legs), time),
      ...(previous ? truckPositions(previous.trucks.flatMap((t) => t.legs), time) : []),
    ].map(({ position }) => viewport.project(position));
    return [...candidates]
      .sort((a, b) => priority(b) - priority(a))
      .filter((c) => {
        const [x, y] = viewport.project([c.lon, c.lat]);
        const width = c.name.length * (mini ? 6.5 : 7.5) + 8;
        const box = {
          left: x + 12,
          right: x + 12 + width,
          top: y + 8,
          bottom: y + (mini ? 25 : 28),
        };
        if (
          box.left < 4 ||
          box.right > size.width - 4 ||
          box.top < 4 ||
          box.bottom > size.height - 4
        )
          return false;
        // Keep labels clear of the title/pill strip and the legend/story
        // strip, which sit on top of the canvas as static chrome.
        if (!mini && (box.top < 80 || box.bottom > size.height - 132))
          return false;
        if (
          occupied.some(
            (b) =>
              box.left < b.right &&
              box.right > b.left &&
              box.top < b.bottom &&
              box.bottom > b.top,
          )
        )
          return false;
        if (
          truckScreen.some(
            ([tx, ty]) =>
              tx > box.left - truckPad &&
              tx < box.right + truckPad &&
              ty > box.top - truckPad &&
              ty < box.bottom + truckPad,
          )
        )
          return false;
        occupied.push(box);
        return true;
      });
  }, [scenario, plan, previous, mini, viewState, size, time]);
  // Keep geometry references stable while only opacity changes on each frame.
  const currentLegs = useMemo(() => plan.trucks.flatMap((t) => t.legs), [plan]);
  const oldLegs = useMemo(
    () => previous?.trucks.flatMap((t) => t.legs) ?? [],
    [previous],
  );
  const currentGroups = useMemo(() => splitLegs(currentLegs), [currentLegs]);
  const oldGroups = useMemo(() => splitLegs(oldLegs), [oldLegs]);
  const positions = useMemo(
    () => truckPositions(currentLegs, time),
    [currentLegs, time],
  );
  const oldPositions = useMemo(
    () => truckPositions(oldLegs, time),
    [oldLegs, time],
  );
  const dots = useMemo(
    () =>
      mini
        ? scenario.cities.filter((c) =>
            currentLegs.some((l) => l.from === c.id || l.to === c.id),
          )
        : scenario.cities,
    [scenario, currentLegs, mini],
  );
  const city = (id: string) => scenario.cities.find((c) => c.id === id)!;
  const layers = useMemo(() => {
    const routeLayers = (groups: LegGroups, opacity: number, suffix: string) =>
      (["loaded", "empty"] as const).map(
        (kind) =>
          new PathLayer<Leg, PathStyleExtensionProps<Leg>>({
            id: `${suffix}-${kind}`,
            data: groups[kind],
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
    const trips = (data: Leg[], opacity: number, suffix: string) =>
      new TripsLayer<Leg>({
        id: `trips-${suffix}`,
        data,
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
        opacity: 0.95 * opacity,
      });
    const markers = (data: TruckPosition[], opacity: number, suffix: string) =>
      new ScatterplotLayer<TruckPosition>({
        id: `trucks-${suffix}`,
        data,
        getPosition: (d) => d.position,
        getRadius: 7,
        radiusUnits: "pixels",
        getFillColor: [169, 155, 224],
        stroked: true,
        getLineColor: [255, 253, 249],
        lineWidthMinPixels: 2,
        opacity,
        pickable: opacity > 0.5,
        onClick: (info) => info.object && onSelect(info.object.truck_id),
      });
    return [
      ...(previous ? routeLayers(oldGroups, 1 - blend, "old") : []),
      ...routeLayers(currentGroups, blend, "current"),
      ...(previous ? [trips(oldLegs, 1 - blend, "old")] : []),
      trips(currentLegs, blend, "current"),
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
      new ScatterplotLayer({
        id: "cities",
        data: dots,
        getPosition: (c) => [c.lon, c.lat],
        getRadius: mini ? 3 : 4,
        radiusUnits: "pixels",
        getFillColor: [250, 247, 242],
        getLineColor: [122, 112, 100],
        stroked: true,
        lineWidthMinPixels: 1.5,
        pickable: true,
      }),
      new TextLayer<City>({
        id: "labels",
        data: labelCities,
        getPosition: (c) => [c.lon, c.lat],
        getText: (c) => c.name,
        getSize: mini ? 10 : 12,
        characterSet: "auto",
        fontSettings: { sdf: true },
        getColor: [74, 66, 56],
        getPixelOffset: [12, 16],
        fontWeight: 500,
        fontFamily: "Inter, sans-serif",
        getTextAnchor: "start",
        outlineWidth: 0.12,
        outlineColor: [250, 247, 242, 230],
      }),
      ...(previous ? [markers(oldPositions, 1 - blend, "old")] : []),
      markers(positions, blend, "current"),
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
    labelCities,
    currentGroups,
    oldGroups,
    currentLegs,
    oldLegs,
    positions,
    oldPositions,
    dots,
  ]);
  return (
    <div
      ref={mapRoot}
      data-testid="map-canvas"
      data-min-zoom={initialZoom.toFixed(4)}
      data-max-zoom="7"
      data-max-bounds="60,2,100,38"
      data-view-zoom={viewState.zoom.toFixed(4)}
      data-view-longitude={viewState.longitude.toFixed(4)}
      data-view-latitude={viewState.latitude.toFixed(4)}
      data-basemap-labels-visible={basemapLabelCount}
      data-transition-progress={blend.toFixed(4)}
      data-transitioning={Boolean(previous)}
      data-basemap-status={
        mapFailed ? "unavailable" : mapReady ? "ready" : "loading"
      }
      className="map-canvas"
    >
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState }) =>
          setViewState(constrainView(viewState as MapViewState))
        }
        controller={{ dragRotate: false, touchRotate: false }}
        layers={layers}
        getCursor={({ isHovering }) => (isHovering ? "pointer" : "grab")}
      >
        <Map
          ref={mapRef}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
          }}
          minZoom={initialZoom}
          maxZoom={7}
          mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
          attributionControl={false}
          onLoad={(e) => {
            const map = e.target;
            for (const layer of map.getStyle().layers || []) {
              if (layer.type === "symbol")
                map.setLayoutProperty(layer.id, "visibility", "none");
            }
            setBasemapLabelCount(
              (map.getStyle().layers || []).filter(
                (layer) =>
                  layer.type === "symbol" &&
                  map.getLayoutProperty(layer.id, "visibility") !== "none",
              ).length,
            );
            map.resize();
            requestAnimationFrame(() => map.resize());
          }}
          onIdle={() => setMapReady(true)}
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
            left: Math.max(8, Math.min(hover.x + 16, size.width - 300)),
            top: Math.max(10, Math.min(hover.y - 80, size.height - 160)),
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
          {hover.object.reason && (
            <span className="tooltip-reason">
              <Sparkles size={12} />
              {explanation(hover.object.reason)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
