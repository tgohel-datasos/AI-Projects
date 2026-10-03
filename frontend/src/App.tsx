import { FormEvent, useEffect, useState } from "react";
import { createPlan, getWorkflow, Workflow } from "./api";

type CityRecord = {
  name?: string;
  countryCode?: string;
  adminRegion?: string;
  admin1?: string;
  region?: string;
};

function IndianCityField({
  id,
  label,
  value,
  onChange
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const [cities, setCities] = useState<CityRecord[]>([]);
  const [searchState, setSearchState] = useState<"idle" | "loading" | "ready" | "unavailable">("idle");

  useEffect(() => {
    const query = value.trim();
    if (query.length < 2) {
      setCities([]);
      setSearchState("idle");
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearchState("loading");
      try {
        const url = new URL("https://countries.dev/cities");
        url.searchParams.set("country", "IN");
        url.searchParams.set("q", query);
        url.searchParams.set("limit", "12");
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) throw new Error(`City search returned ${response.status}`);
        const payload: unknown = await response.json();
        const rows = Array.isArray(payload)
          ? payload
          : (payload as { results?: unknown[]; data?: unknown[] })?.results ??
            (payload as { data?: unknown[] })?.data ?? [];
        const matches = rows.filter((row): row is CityRecord => {
          if (!row || typeof row !== "object") return false;
          const city = row as CityRecord;
          return typeof city.name === "string" && (!city.countryCode || city.countryCode.toUpperCase() === "IN");
        });
        setCities(matches);
        setSearchState("ready");
      } catch (error) {
        if (controller.signal.aborted) return;
        setCities([]);
        setSearchState("unavailable");
      }
    }, 300);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [value]);

  const options = cities.map((city) => {
    const region = city.adminRegion || city.admin1 || city.region;
    return `${city.name}${region ? `, ${region}` : ""}, India`;
  });

  return (
    <div>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        list={`${id}-cities`}
        value={value}
        autoComplete="off"
        placeholder="Search Indian cities or enter a place"
        onChange={(event) => onChange(event.target.value)}
      />
      <datalist id={`${id}-cities`}>
        {options.map((option) => <option key={option} value={option} />)}
      </datalist>
      <small className="city-hint" aria-live="polite">
        {searchState === "loading" && "Searching Indian cities…"}
        {searchState === "ready" && cities.length > 0 && `${cities.length} suggestions · select one or keep typing`}
        {searchState === "ready" && cities.length === 0 && "No city suggestions; you can still enter a place manually."}
        {searchState === "unavailable" && "City suggestions are unavailable; manual entry still works."}
      </small>
    </div>
  );
}

const defaultTrip = {
  origin: "Ahmedabad",
  destination: "Munnar",
  adults: 12,
  children: 2,
  child_ages: "6,9",
  travel_mode: "flight",
  start_date: "2026-11-08",
  end_date: "2026-11-15",
  hotel_category: "5 Star",
  room_occupancy: 2,
  food_preference: "Jain",
  payment_method: "Credit Card",
  hotel_cancellation_required: true,
  max_airport_distance_km: 30,
  budget_min: 300000,
  budget_max: 500000,
  currency: "INR"
};

const terminalStatuses = new Set(["completed", "failed", "needs_input", "needs_review"]);

type JsonObject = Record<string, any>;
type PlanSelection = {
  transport_id: string | null;
  hotel_id: string | null;
  itinerary_by_day: Record<string, string[]>;
  extras: { food_preference: string; room_split: number[]; activities: Record<string, boolean> };
};
type FinalResponse = {
  request_id: string;
  status: "success" | "needs_review" | "failed";
  traveler: { name: string | null; adults: number; children: number; child_ages: number[] };
  trip: { from: string; to: string; start_date: string; end_date: string; nights: number; mode: string };
  feasibility: { is_possible: boolean; note: string | null; distance_km: number | null; airport: { code: string | null; distance_km: number | null } };
  weather: { summary: string | null; temp_range_c: [number | null, number | null] };
  transport: { mode: string | null; quote_status: "pending" | "available"; options: JsonObject[]; airport_transfer: JsonObject | null; airport_limit_km: number | null };
  hotel: { category: string | null; rooms: number | null; occupancy: number | null; cancellation_policy_required: boolean; quote_status: "pending" | "available"; options: JsonObject[] };
  itinerary: JsonObject[];
  health: { summary: string | null; considerations: string[]; medical_kit: string[] };
  budget: { currency: "INR"; min: number | null; max: number | null; estimated_total: number | null; within_limit: boolean | null };
  selection: PlanSelection;
  final_plan: JsonObject;
  warnings: string[];
  errors: string[];
};

const object = (value: unknown): JsonObject => value && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : {};
const finite = (value: unknown): number | null => typeof value === "number" && Number.isFinite(value) ? value : null;
const cleanString = (value: unknown): string | null => typeof value === "string" && value.trim() ? value.trim() : null;
const stringList = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0) : [];
const emptySelection: PlanSelection = { transport_id: null, hotel_id: null, itinerary_by_day: {}, extras: { food_preference: "", room_split: [], activities: {} } };

function titleCaseMode(value: string | null): string | null {
  if (!value) return null;
  return value.toLowerCase().split(/\s+/).map((word) => word ? word[0].toUpperCase() + word.slice(1) : word).join(" ");
}

function makeRoomSplit(adults: number, children: number, occupancy: number, requestedRooms?: number): number[] {
  const travelers = Math.max(0, adults + children);
  const minimum = Math.max(1, Math.ceil(travelers / Math.max(1, occupancy)));
  const rooms = Math.max(minimum, Math.min(travelers || 1, requestedRooms ?? minimum));
  const split = Array.from({ length: rooms }, () => 0);
  for (let i = 0; i < travelers; i += 1) split[i % rooms] += 1;
  return split;
}

function dateOffset(start: string, offset: number): string | null {
  const date = new Date(`${start}T00:00:00Z`);
  if (!Number.isFinite(date.getTime())) return null;
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}

function buildFinalResponse(wf: Workflow, fallback: { form: typeof defaultTrip; name: string }, selected?: PlanSelection): FinalResponse {
  const request = object(wf.request);
  const requestedTrip = object(request.trip ?? request);
  const tripInput = { ...fallback.form, ...requestedTrip };
  const summary = object(wf.plan?.summary);
  const plannerExecution = wf.executions.find((execution) => execution.agent_id === "travel_planner");
  const plannerResult = object(object(plannerExecution?.output).result);
  const feasibility = object(summary.trip_status);
  const transportData = object(summary.transport_details);
  const airport = object(transportData.servicing_airport);
  const hotelData = object(summary.hotel_details);
  const hotelRequirement = object(hotelData.roomRequirement);
  const finance = object(summary.costing_and_discounts);
  const totals = object(finance.totals);
  const weatherData = object(summary.weather_and_climate);
  const weatherTemps = object(weatherData.average_temperature_celsius);
  const sightseeing = object(summary.sightseeing_and_guide);
  const healthData = object(object(summary.lifestyle_and_safety_advisories).health_and_wellness);
  const healthSummary = object(healthData.health_summary);
  const healthFlags = object(healthData.health_flags);
  const docs = object(summary.mandatory_documents);
  const audit = object(summary.validation_summary);
  const auditWarnings = stringList(audit.flags_or_warnings);
  const hotelCancellationRequired = Boolean(tripInput.hotel_cancellation_required);
  const status: FinalResponse["status"] = wf.status === "failed"
    ? "failed"
    : wf.status === "needs_review" || wf.status === "needs_input"
      ? "needs_review"
      : "success";

  const requestedCategory = cleanString(tripInput.hotel_category);
  const hotelOptions = (Array.isArray(hotelData.hotels) ? hotelData.hotels : []).map((value: unknown, index: number) => {
    const option = object(value);
    const location = object(option.location);
    const pricing = object(option.pricing);
    const rawName = cleanString(option.name);
    return {
      id: `hotel-${index + 1}`,
      name: rawName && rawName.toLowerCase() !== "hotel" ? rawName : null,
      address: cleanString(location.address),
      area: cleanString(location.area ?? location.neighborhood ?? location.suburb ?? location.locality),
      category: cleanString(option.category),
      category_verified: String(option.category_verification ?? "").toUpperCase() !== "UNVERIFIED",
      rooms: finite(object(option.room).rooms) ?? finite(hotelRequirement.roomsRequired),
      occupancy: finite(object(option.room).occupancy) ?? finite(tripInput.room_occupancy),
      price: finite(pricing.totalCost),
      currency: cleanString(pricing.currency) ?? "INR",
      cancellation_status: cleanString(object(option.cancellation).status),
      quote_status: finite(pricing.totalCost) !== null && ["AVAILABLE", "QUOTED", "VERIFIED", "VERIFIED_LIVE", "LIVE"].includes(String(pricing.status ?? "").toUpperCase()) ? "available" : "pending",
      recommended: false,
    };
  });
  const rawHotels = Array.isArray(hotelData.hotels) ? hotelData.hotels.map(object) : [];
  const airportDistance = finite(airport.distance_to_destination_km);
  const airportLimit = finite(tripInput.max_airport_distance_km);
  const rawTransportOptions = Array.isArray(transportData.options) ? transportData.options.map(object) : [];
  const transportOptions: JsonObject[] = rawTransportOptions.map((option, index) => {
    const carrier = cleanString(option.airline);
    return {
      id: `transport-${index + 1}`,
      mode: titleCaseMode(cleanString(option.mode)),
      carrier: carrier && !/indicative|unavailable|unknown/i.test(carrier) ? carrier : null,
      departure_date: cleanString(option.departure_date),
      return_date: cleanString(option.return_date),
      origin_airport: cleanString(option.origin_airport),
      destination_airport: cleanString(option.destination_airport),
      price: finite(option.total),
      duration: cleanString(option.duration),
      currency: cleanString(option.currency) ?? "INR",
      route_summary: cleanString(option.route_summary),
      notes: cleanString(option.notes),
      official_search_url: cleanString(option.official_search_url),
      train_number: cleanString(option.train_number),
      origin_station: cleanString(option.origin_station),
      destination_station: cleanString(option.destination_station),
      quote_status: finite(option.total) !== null && ["VERIFIED_LIVE", "LIVE", "QUOTED"].includes(String(option.data_status ?? option.pricing_status ?? "").toUpperCase()) ? "available" : "pending",
      recommended: false,
    };
  });
  const transfer = object(transportData.airport_transfer);
  if (Object.keys(transfer).length > 0 && transportOptions.some((option) => String(option.mode).toLowerCase() === "train")) {
    const train = transportOptions.find((option) => String(option.mode).toLowerCase() === "train")!;
    transportOptions.push({
      ...train,
      id: "transport-train-road",
      mode: "Train + road transfer",
      price: finite(train.price) !== null && finite(transfer.total) !== null ? Number(train.price) + Number(transfer.total) : null,
      quote_status: train.quote_status === "available" && finite(transfer.total) !== null ? "available" : "pending",
      recommended: false,
      includes_road_transfer: true,
    });
  }
  const activities = Array.isArray(sightseeing.guidedActivities) ? sightseeing.guidedActivities : [];
  const routeOverview = object(summary.route_overview);
  const tripDays = Math.max(1, finite(routeOverview.duration_days) ?? ((finite(routeOverview.duration_nights) ?? 0) + 1));
  const itinerary: JsonObject[] = activities.slice(0, tripDays * 4).flatMap((value: unknown, index: number): JsonObject[] => {
    const activity = object(value);
    const name = cleanString(activity.name);
    return name ? [{
      id: `activity-${index + 1}`,
      name,
      day: Math.min(tripDays, Math.floor(index / 4) + 1),
      family_friendly: typeof activity.familyFriendly === "boolean" ? activity.familyFriendly : null,
      guide_required: cleanString(activity.guideRequired),
      price: finite(activity.total),
      currency: cleanString(activity.currency) ?? "INR",
    }] : [];
  });

  const quoteTotal = finite(totals.grandTotal);
  const tripStart = String(tripInput.start_date ?? "");
  const tripEnd = String(tripInput.end_date ?? "");
  const childAges = Array.isArray(tripInput.child_ages) ? tripInput.child_ages.filter((age: unknown): age is number => typeof age === "number" && Number.isInteger(age)) : [];
  const corridorDistance = finite(feasibility.distance_km) ?? finite(plannerResult.corridor_distance_km);
  const warnings = new Set<string>();
  if (airportDistance !== null && airport.within_limit === false) warnings.add("The nearest airport is outside your distance limit; review the onward transfer.");
  if (auditWarnings.some((warning) => /hotel cancellation|free-cancellation|free cancellation/i.test(warning)) && !hotelCancellationRequired) {
    warnings.add("Hotel cancellation terms could not be verified.");
  }

  const minBudget = finite(tripInput.budget_min);
  const maxBudget = finite(tripInput.budget_max);
  const requestedMode = String(tripInput.travel_mode ?? "").toLowerCase();
  const defaultTransport = airportDistance !== null && airportLimit !== null && airportDistance > airportLimit
    ? transportOptions.find((option) => option.id === "transport-train-road") ?? transportOptions.find((option) => String(option.mode).toLowerCase().includes(requestedMode)) ?? transportOptions[0]
    : transportOptions.find((option) => String(option.mode).toLowerCase() === requestedMode) ?? transportOptions[0];
  if (defaultTransport) defaultTransport.recommended = true;
  const defaultHotel = hotelOptions.find((option) => option.category === requestedCategory) ?? hotelOptions[0];
  if (defaultHotel) defaultHotel.recommended = true;
  const itineraryByDay: Record<string, string[]> = {};
  for (let day = 1; day <= tripDays; day += 1) itineraryByDay[`day-${day}`] = itinerary.filter((activity) => activity.day === day).map((activity) => activity.id);
  const defaults: PlanSelection = {
    transport_id: defaultTransport?.id ?? null,
    hotel_id: defaultHotel?.id ?? null,
    itinerary_by_day: itineraryByDay,
    extras: {
      food_preference: String(tripInput.food_preference ?? ""),
      room_split: makeRoomSplit(finite(tripInput.adults) ?? 0, finite(tripInput.children) ?? 0, finite(tripInput.room_occupancy) ?? 2),
      activities: Object.fromEntries(itinerary.map((activity) => [activity.id, true])),
    },
  };
  const selection = selected ?? defaults;
  const chosenTransport = transportOptions.find((option) => option.id === selection.transport_id) ?? null;
  const chosenHotel = hotelOptions.find((option) => option.id === selection.hotel_id) ?? null;
  const selectedActivityIds = new Set(Object.values(selection.itinerary_by_day).flat());
  const chosenItinerary: JsonObject[] = Object.entries(selection.itinerary_by_day).flatMap(([dayKey, ids]) => ids
    .filter((id) => selection.extras.activities[id] !== false && selectedActivityIds.has(id))
    .flatMap((id) => {
      const activity = itinerary.find((item) => item.id === id);
      return activity ? [{ ...activity, day: Number(dayKey.replace("day-", "")) }] : [];
    }));
  const pendingQuotes: string[] = [];
  const costItems: JsonObject[] = [];
  const chosenTransportPrice = finite(chosenTransport?.price);
  if (chosenTransport) {
    if (chosenTransportPrice === null) pendingQuotes.push("Transport");
    else costItems.push({ item: "Transport", amount: chosenTransportPrice, currency: "INR" });
  }
  if (chosenHotel) {
    const hotelPrice = finite(chosenHotel.price);
    if (hotelPrice === null) pendingQuotes.push("Hotel");
    else costItems.push({ item: "Hotel", amount: hotelPrice, currency: "INR" });
  }
  chosenItinerary.forEach((activity) => {
    const price = finite(activity.price);
    if (price === null) pendingQuotes.push(String(activity.name));
    else costItems.push({ item: String(activity.name), amount: price, currency: "INR" });
  });
  if (chosenTransport?.includes_road_transfer && finite(transfer.total) === null) pendingQuotes.push("Airport road transfer");
  const knownSubtotal = costItems.length ? costItems.reduce((sum, item) => sum + Number(item.amount), 0) : null;
  const selectedTotal = pendingQuotes.length ? null : knownSubtotal;
  const withinLimit = selectedTotal === null || maxBudget === null ? null : selectedTotal <= maxBudget;
  const finalPlan = {
    transport: chosenTransport,
    hotel: chosenHotel ? { ...chosenHotel, rooms: selection.extras.room_split.length, room_split: selection.extras.room_split } : null,
    itinerary: Array.from({ length: tripDays }, (_, index) => {
      const day = index + 1;
      return { day, date: dateOffset(tripStart, index), places: chosenItinerary.filter((activity) => activity.day === day) };
    }),
    extras: selection.extras,
    cost_summary: { currency: "INR", items: costItems, known_subtotal: knownSubtotal, selected_total: selectedTotal, budget_min: minBudget, budget_max: maxBudget, within_limit: withinLimit, pending_quotes: pendingQuotes },
    pending_quotes: pendingQuotes,
    warnings: [...warnings],
  };
  return {
    request_id: wf.id,
    status,
    traveler: {
      name: (() => {
        const travelerName = cleanString(request.user_display_name) ?? cleanString(fallback.name);
        return travelerName && travelerName.toLowerCase() !== "guest" ? travelerName : null;
      })(),
      adults: finite(tripInput.adults) ?? 0,
      children: finite(tripInput.children) ?? 0,
      child_ages: childAges,
    },
    trip: {
      from: String(tripInput.origin ?? ""),
      to: String(tripInput.destination ?? ""),
      start_date: tripStart,
      end_date: tripEnd,
      nights: finite(object(summary.route_overview).duration_nights) ?? Math.max(0, Math.round((Date.parse(`${tripEnd}T00:00:00Z`) - Date.parse(`${tripStart}T00:00:00Z`)) / 86400000)),
      mode: String(tripInput.travel_mode ?? ""),
    },
    feasibility: {
      is_possible: Boolean(feasibility.is_possible),
      note: cleanString(feasibility.feasibility_note),
      distance_km: corridorDistance,
      airport: { code: cleanString(airport.iata), distance_km: airportDistance },
    },
    weather: {
      summary: cleanString(object(weatherData.weather_policy).summary),
      temp_range_c: [finite(weatherTemps.min), finite(weatherTemps.max)],
    },
    transport: {
      mode: titleCaseMode(cleanString(transportData.transport_mode)),
      quote_status: rawTransportOptions.some((option) => finite(option.total) !== null && ["VERIFIED_LIVE", "LIVE", "QUOTED"].includes(String(option.data_status ?? option.pricing_status ?? "").toUpperCase())) ? "available" : "pending",
      options: transportOptions,
      airport_transfer: (() => {
        return Object.keys(transfer).length ? {
          description: cleanString(transfer.description),
          distance_km: finite(transfer.distance_km),
          total: finite(transfer.total),
          currency: cleanString(transfer.currency) ?? "INR",
        } : null;
      })(),
      airport_limit_km: airportLimit,
    },
    hotel: {
      category: cleanString(tripInput.hotel_category),
      rooms: selection.extras.room_split.length || finite(hotelRequirement.roomsRequired) || Math.ceil(((finite(tripInput.adults) ?? 0) + (finite(tripInput.children) ?? 0)) / (finite(tripInput.room_occupancy) ?? 1)),
      occupancy: finite(tripInput.room_occupancy),
      cancellation_policy_required: hotelCancellationRequired,
      quote_status: rawHotels.some((option) => {
        const pricing = object(option.pricing);
        return finite(pricing.totalCost) !== null && ["AVAILABLE", "QUOTED", "VERIFIED", "VERIFIED_LIVE", "LIVE"].includes(String(pricing.status ?? "").toUpperCase());
      }) ? "available" : "pending",
      options: hotelOptions,
    },
    itinerary,
    health: {
      summary: cleanString(healthSummary.travel_health_preparedness),
      considerations: stringList(object(healthData.traveler_considerations).adults && object(object(healthData.traveler_considerations).adults).considerations)
        .concat(stringList(object(object(healthData.traveler_considerations).children).considerations)),
      medical_kit: Array.isArray(healthData.medical_kit) ? healthData.medical_kit.map((item: unknown) => cleanString(object(item).item)).filter((item: string | null): item is string => item !== null) : [],
    },
    budget: {
      currency: "INR",
      min: minBudget,
      max: maxBudget,
      estimated_total: selectedTotal,
      within_limit: withinLimit,
    },
    selection,
    final_plan: finalPlan,
    warnings: [...warnings],
    errors: status === "failed" ? ["The travel request could not be completed. Please submit again."] : [],
  };
}

export default function App() {
  const [form, setForm] = useState(defaultTrip);
  const [name, setName] = useState("Guest");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wf, setWf] = useState<Workflow | null>(null);
  const [copied, setCopied] = useState(false);
  const [selection, setSelection] = useState<PlanSelection>(emptySelection);
  const [selectionWorkflowId, setSelectionWorkflowId] = useState<string | null>(null);
  const [screen, setScreen] = useState<"builder" | "final">("builder");
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (!wf?.id) return;
    if (terminalStatuses.has(wf.status)) return;
    const t = setInterval(async () => {
      try {
        setWf(await getWorkflow(wf.id));
      } catch {
        /* keep last snapshot */
      }
    }, 1200);
    return () => clearInterval(t);
  }, [wf?.id, wf?.status]);

  useEffect(() => {
    if (!wf?.plan || selectionWorkflowId === wf.id) return;
    const defaults = buildFinalResponse(wf, { form, name }).selection;
    setSelection(defaults);
    setSelectionWorkflowId(wf.id);
    setScreen("builder");
    setConfirmed(false);
  }, [wf?.id, Boolean(wf?.plan)]);

  const finalResponse = wf?.plan ? buildFinalResponse(wf, { form, name }, selectionWorkflowId === wf.id ? selection : undefined) : null;
  const selectedTransport = finalResponse?.transport.options.find((option) => option.id === finalResponse.selection.transport_id) ?? null;
  const selectedHotel = finalResponse?.hotel.options.find((option) => option.id === finalResponse.selection.hotel_id) ?? null;
  const costSummary = object(finalResponse?.final_plan.cost_summary);
  const pendingQuotes = stringList(costSummary.pending_quotes);
  const canReviewFinalPlan = Boolean(selectedTransport && selectedHotel);
  const nearestAirportTooFar = finalResponse?.feasibility.airport.distance_km != null
    && finalResponse.transport.airport_limit_km != null
    && finalResponse.feasibility.airport.distance_km > finalResponse.transport.airport_limit_km;
  const isWorking = Boolean(wf && !terminalStatuses.has(wf.status));

  function updateSelection(change: (current: PlanSelection) => PlanSelection) {
    setSelection((current) => change(current));
  }

  function toggleActivity(activityId: string, checked: boolean) {
    updateSelection((current) => ({ ...current, extras: { ...current.extras, activities: { ...current.extras.activities, [activityId]: checked } } }));
  }

  function moveActivity(dayKey: string, index: number, offset: number) {
    updateSelection((current) => {
      const items = [...(current.itinerary_by_day[dayKey] ?? [])];
      const target = index + offset;
      if (target < 0 || target >= items.length) return current;
      [items[index], items[target]] = [items[target], items[index]];
      return { ...current, itinerary_by_day: { ...current.itinerary_by_day, [dayKey]: items } };
    });
  }

  function reviewFinalPlan() {
    if (!canReviewFinalPlan) return;
    setConfirmed(false);
    setScreen("final");
  }

  async function copyFinalJson() {
    if (!finalResponse) return;
    await navigator.clipboard.writeText(JSON.stringify(finalResponse, null, 2));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const ages = form.child_ages
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean)
        .map((x) => Number(x));
      const created = await createPlan({
        user_display_name: name,
        trip: {
          ...form,
          adults: Number(form.adults),
          children: Number(form.children),
          child_ages: ages,
          room_occupancy: Number(form.room_occupancy),
          max_airport_distance_km: Number(form.max_airport_distance_km),
          budget_min: Number(form.budget_min),
          budget_max: Number(form.budget_max)
        }
      });
      setWf(created);
    } catch (err) {
      setError("We couldn't submit your request. Check the details and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Multi-Agent Travel Planner</h1>
        <p>Orchestrator selects specialists, runs them in parallel where safe, then Finance and Validator assemble the plan.</p>
      </header>
      {screen === "builder" && <div className="grid">
        <form className="card" onSubmit={onSubmit}>
          <h2>Travel request</h2>
          <label>Your name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} />
          <div className="row">
            <IndianCityField id="origin" label="From" value={form.origin} onChange={(origin) => setForm((current) => ({ ...current, origin }))} />
            <IndianCityField id="destination" label="To" value={form.destination} onChange={(destination) => setForm((current) => ({ ...current, destination }))} />
          </div>
          <p className="city-attribution">Indian city suggestions from <a href="https://countries.dev/cities-api" target="_blank" rel="noreferrer">GeoNames via countries.dev</a>. You can also enter another place manually.</p>
          <div className="row">
            <div>
              <label>Adults</label>
              <input type="number" min={1} value={form.adults} onChange={(e) => setForm({ ...form, adults: Number(e.target.value) })} />
            </div>
            <div>
              <label>Children</label>
              <input type="number" min={0} value={form.children} onChange={(e) => setForm({ ...form, children: Number(e.target.value) })} />
            </div>
          </div>
          <label>Child ages (comma separated)</label>
          <input value={form.child_ages} onChange={(e) => setForm({ ...form, child_ages: e.target.value })} />
          <div className="row">
            <div>
              <label>Start</label>
              <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            </div>
            <div>
              <label>End</label>
              <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
            </div>
          </div>
          <div className="row">
            <div>
              <label>Mode</label>
              <select value={form.travel_mode} onChange={(e) => setForm({ ...form, travel_mode: e.target.value })}>
                <option value="flight">Flight</option>
                <option value="train">Train</option>
                <option value="bus">Bus</option>
                <option value="car">Car</option>
                <option value="multi">Multi</option>
              </select>
            </div>
            <div>
              <label>Hotel category</label>
              <select value={form.hotel_category} onChange={(e) => setForm({ ...form, hotel_category: e.target.value })}>
                <option>5 Star</option>
                <option>4 Star</option>
                <option>3 Star</option>
                <option>Villa</option>
                <option>Resorts</option>
              </select>
            </div>
          </div>
          <div className="row">
            <div>
              <label>Food</label>
              <input value={form.food_preference} onChange={(e) => setForm({ ...form, food_preference: e.target.value })} />
            </div>
            <div>
              <label>Payment</label>
              <select value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
                <option>Credit Card</option>
                <option>Debit Card</option>
                <option>UPI</option>
                <option>Cash</option>
                <option>Google Pay</option>
              </select>
            </div>
          </div>
          <div className="row">
            <div>
              <label>Budget min (INR)</label>
              <input type="number" value={form.budget_min} onChange={(e) => setForm({ ...form, budget_min: Number(e.target.value) })} />
            </div>
            <div>
              <label>Budget max (INR)</label>
              <input type="number" value={form.budget_max} onChange={(e) => setForm({ ...form, budget_max: Number(e.target.value) })} />
            </div>
          </div>
          <label>Max airport distance (km)</label>
          <input type="number" value={form.max_airport_distance_km} onChange={(e) => setForm({ ...form, max_airport_distance_km: Number(e.target.value) })} />
          <label>
            <input
              type="checkbox"
              checked={form.hotel_cancellation_required}
              onChange={(e) => setForm({ ...form, hotel_cancellation_required: e.target.checked })}
              style={{ width: "auto", marginRight: 8 }}
            />
            Hotel cancellation policy required
          </label>
          <button type="submit" disabled={busy}>
            {busy ? "Submitting…" : "Submit"}
          </button>
          {error && <div className="result-banner failed" role="alert"><strong>Request not submitted</strong><p>{error}</p></div>}
        </form>

        <section className="card results-panel" aria-live="polite">
          {!wf && <><h2>Your results</h2><p className="muted">Submit a travel request to build your itinerary.</p></>}
          {isWorking && <><h2>Preparing your trip…</h2><p className="muted">Your specialists are checking the request. This view will update automatically.</p></>}
          {wf?.status === "failed" && !finalResponse && <div className="result-banner failed" role="alert"><strong>We couldn’t finish this plan</strong><p>Please submit again. If the issue continues, check the service logs.</p></div>}
          {finalResponse && <>
            <div className="result-heading">
              <div>
                <h2>Travel plan</h2>
                <p className="result-route">{finalResponse.trip.from} <span aria-hidden="true">→</span> {finalResponse.trip.to}</p>
                <p className="muted">{finalResponse.trip.start_date} – {finalResponse.trip.end_date} · {finalResponse.trip.nights} nights · {finalResponse.traveler.adults} adults, {finalResponse.traveler.children} children{finalResponse.traveler.child_ages.length ? ` (ages ${finalResponse.traveler.child_ages.join(", ")})` : ""}</p>
              </div>
              <span className={`status-pill ${finalResponse.status}`}>{finalResponse.status === "success" ? "Success" : finalResponse.status === "needs_review" ? "Needs review" : "Failed"}</span>
            </div>
            {finalResponse.status === "failed" && <div className="result-banner failed" role="alert"><strong>We couldn’t finish this plan</strong><p>Please submit again. If the issue continues, check the service logs.</p></div>}

            <div className="result-cards">
              <article className="result-card"><h3>Feasibility</h3><b>{finalResponse.feasibility.is_possible ? "Possible" : "Needs another route"}</b><p>{finalResponse.feasibility.note ?? "Route details are not available."}</p><p>Nearest airport: {finalResponse.feasibility.airport.code ?? "Unknown"} · {finalResponse.feasibility.airport.distance_km == null ? "Distance unavailable" : `${finalResponse.feasibility.airport.distance_km} km`}</p></article>
              <article className="result-card"><h3>Weather</h3><p>{finalResponse.weather.summary ?? "Weather information unavailable."}</p><p>Typical range: {finalResponse.weather.temp_range_c[0] == null || finalResponse.weather.temp_range_c[1] == null ? "Unavailable" : `${finalResponse.weather.temp_range_c[0]}–${finalResponse.weather.temp_range_c[1]} °C`}</p></article>
              <article className="result-card selectable-section"><h3>Transport</h3>
                {nearestAirportTooFar && <div className="inline-warning"><span>Nearest airport is {finalResponse.feasibility.airport.distance_km} km away, beyond your {finalResponse.transport.airport_limit_km} km limit.</span>{selection.transport_id === "transport-train-road" ? <b>Train + road selected</b> : finalResponse.transport.options.some((option) => option.id === "transport-train-road") && <button type="button" className="text-action" onClick={() => updateSelection((current) => ({ ...current, transport_id: "transport-train-road" }))}>Switch to Train + road</button>}</div>}
                {finalResponse.transport.options.length > 0 ? <div className="option-list">{finalResponse.transport.options.map((option) => <label className={`choice-card ${selection.transport_id === option.id ? "selected" : ""}`} key={option.id}>
                  <input type="radio" name="transport-choice" checked={selection.transport_id === option.id} onChange={() => updateSelection((current) => ({ ...current, transport_id: option.id }))} />
                  <span className="choice-copy"><b>{option.mode ?? "Transport"}</b>{option.recommended && <em>Recommended</em>}{option.carrier && <small>{option.carrier}</small>}{option.route_summary && <small>{option.route_summary}</small>}{option.train_number && <small>Train {option.train_number}{option.origin_station && option.destination_station ? ` · ${option.origin_station} → ${option.destination_station}` : ""}</small>}{option.notes && <small>{option.notes}</small>}{option.includes_road_transfer && <small>Includes onward road transfer</small>}{option.official_search_url && <a className="provider-link" href={option.official_search_url} target="_blank" rel="noreferrer">Search trains on IRCTC ↗</a>}</span>
                  <span className="choice-meta">{option.quote_status === "available" ? formatInr(finite(option.price)) : <QuoteChip status="pending" />}{option.duration && <small>{option.duration}</small>}</span>
                </label>)}</div> : <p>No transport options available.</p>}
                {finalResponse.transport.airport_transfer && <p>{finalResponse.transport.airport_transfer.description ?? "Airport transfer"}{finalResponse.transport.airport_transfer.distance_km != null ? ` · ${finalResponse.transport.airport_transfer.distance_km} km` : ""}</p>}
              </article>
              <article className="result-card selectable-section"><h3>Hotel</h3><p>{finalResponse.hotel.category ?? "Category not specified"} requested · {selection.extras.room_split.length} rooms</p>
                {finalResponse.hotel.cancellation_policy_required && <span className="warning-chip">Cancellation policy not verified</span>}
                {finalResponse.hotel.options.length > 0 ? <div className="option-list">{finalResponse.hotel.options.map((option) => <label className={`choice-card hotel-choice ${selection.hotel_id === option.id ? "selected" : ""}`} key={option.id}>
                  <input type="radio" name="hotel-choice" checked={selection.hotel_id === option.id} onChange={() => updateSelection((current) => ({ ...current, hotel_id: option.id }))} />
                  <span className="choice-copy"><b>{option.name ?? "Hotel (name pending)"}</b>{option.recommended && <em>Recommended</em>}<small>{option.category_verified ? option.category ?? "Category unavailable" : `${option.category ?? finalResponse.hotel.category ?? "Category"} · unverified`}</small><small>{option.area ? `Area: ${option.area}` : "Area unavailable"}</small><small>{option.address ?? "Address unavailable"}</small><small>{option.rooms ?? selection.extras.room_split.length} rooms × {option.occupancy ?? finalResponse.hotel.occupancy ?? "—"} guests</small><a className="provider-link" href={bookingSearchUrl(finalResponse, selection.extras.room_split.length)} target="_blank" rel="noreferrer">Check current hotel rates ↗</a></span>
                  <span className="choice-meta">{option.quote_status === "available" ? formatInr(finite(option.price)) : <QuoteChip status="pending" />}</span>
                </label>)}</div> : <p>No hotel offers are available yet. The hotel selection is required before review.</p>}
              </article>
              <article className="result-card itinerary-card"><h3>Tour / itinerary</h3>
                {Object.entries(selection.itinerary_by_day).map(([dayKey, activityIds]) => <section className="day-builder" key={dayKey}><h4>Day {dayKey.replace("day-", "")}</h4>{activityIds.length === 0 && <p className="muted">Free day</p>}{activityIds.map((activityId, index) => {
                  const activity = finalResponse.itinerary.find((item) => item.id === activityId);
                  if (!activity) return null;
                  const checked = selection.extras.activities[activityId] !== false;
                  return <div className={`activity-row ${checked ? "" : "disabled"}`} key={activityId}><label><input type="checkbox" checked={checked} onChange={(event) => toggleActivity(activityId, event.target.checked)} /><span>{activity.name}</span>{activity.price == null ? <QuoteChip status="pending" /> : <small>{formatInr(finite(activity.price))}</small>}</label><div className="reorder-actions"><button type="button" aria-label={`Move ${activity.name} up`} disabled={index === 0} onClick={() => moveActivity(dayKey, index, -1)}>↑</button><button type="button" aria-label={`Move ${activity.name} down`} disabled={index === activityIds.length - 1} onClick={() => moveActivity(dayKey, index, 1)}>↓</button></div></div>;
                })}</section>)}
                {finalResponse.itinerary.length === 0 && <p>No itinerary activities available.</p>}
              </article>
              <article className="result-card"><h3>Health</h3><p>{finalResponse.health.summary ?? "General travel guidance."}</p>{finalResponse.health.considerations.length > 0 && <p>{finalResponse.health.considerations.join(" · ")}</p>}</article>
              <article className="result-card extras-card"><h3>Optional extras</h3><label>Food preference<input value={selection.extras.food_preference} onChange={(event) => updateSelection((current) => ({ ...current, extras: { ...current.extras, food_preference: event.target.value } }))} /></label><label>Rooms<input type="number" min={Math.ceil((finalResponse.traveler.adults + finalResponse.traveler.children) / Math.max(1, finalResponse.hotel.occupancy ?? 2))} value={selection.extras.room_split.length} onChange={(event) => updateSelection((current) => ({ ...current, extras: { ...current.extras, room_split: makeRoomSplit(finalResponse.traveler.adults, finalResponse.traveler.children, finalResponse.hotel.occupancy ?? 2, Number(event.target.value)) } }))} /></label><p>Room split: {selection.extras.room_split.join(" + ")} guests</p></article>
              <article className="result-card budget-builder"><h3>Selected total vs budget</h3><p className="total-line">Selected total: {costSummary.selected_total == null ? <QuoteChip status="pending" /> : formatInr(finite(costSummary.selected_total))}</p><p>{costSummary.known_subtotal == null ? "No priced items returned yet." : `Known subtotal: ${formatInr(finite(costSummary.known_subtotal))}`} · Budget: {formatInr(finalResponse.budget.min)}–{formatInr(finalResponse.budget.max)}</p><div className="budget-track"><span style={{ width: `${Math.min(100, Math.max(0, finalResponse.budget.max ? (finite(costSummary.known_subtotal) ?? 0) / finalResponse.budget.max * 100 : 0))}%` }} /></div>{pendingQuotes.length > 0 && <p>Pending quotes: {pendingQuotes.join(", ")}</p>}{nearestAirportTooFar && <p className="inline-warning">Transport plan should account for the airport distance above.</p>}</article>
            </div>
            {!canReviewFinalPlan && <p className="validation-note">Select one transport option and one hotel to review the final plan.</p>}
            <button type="button" className="primary-action" disabled={!canReviewFinalPlan} onClick={reviewFinalPlan}>Review final plan</button>
            <details className="json-details"><summary>View JSON</summary>
              <button type="button" className="copy-button" onClick={copyFinalJson}>{copied ? "Copied" : "Copy"}</button>
              <pre>{JSON.stringify(finalResponse, null, 2)}</pre>
            </details>
          </>}
          {wf && <details className="technical-details" open={isWorking}><summary>Technical details</summary><div className="agents">{wf.executions.map((execution) => <div className="agent" key={execution.id}><div><strong>{execution.agent_id}</strong><div className="agent-meta">{execution.stage} · attempt {execution.attempt}</div></div><span className={`badge ${execution.status}`}>{execution.status}</span></div>)}{wf.executions.length === 0 && <p className="muted">Waiting for the first agent…</p>}</div></details>}
        </section>
      </div>}
      {screen === "final" && finalResponse && <section className="card final-plan-screen" aria-label="Final plan">
        <div className="final-plan-top"><div><h2>Final Plan</h2><p className="result-route">{finalResponse.trip.from} → {finalResponse.trip.to}</p><p className="muted">{finalResponse.trip.start_date} – {finalResponse.trip.end_date} · {finalResponse.trip.nights} nights · {finalResponse.traveler.adults} adults, {finalResponse.traveler.children} children{finalResponse.traveler.child_ages.length ? ` (ages ${finalResponse.traveler.child_ages.join(", ")})` : ""}</p></div><span className={`status-pill ${finalResponse.status}`}>{finalResponse.status === "success" ? "Success" : finalResponse.status === "needs_review" ? "Needs review" : "Failed"}</span></div>
        <div className="final-plan-grid">
          <article className="result-card"><h3>Transport</h3><b>{selectedTransport?.mode ?? "Not selected"}</b>{selectedTransport?.carrier && <p>{selectedTransport.carrier}</p>}{selectedTransport?.price != null ? <p>{formatInr(finite(selectedTransport.price))}</p> : <QuoteChip status="pending" />}{selectedTransport?.route_summary && <p>{selectedTransport.route_summary}</p>}{selectedTransport?.notes && <p>{selectedTransport.notes}</p>}{selectedTransport?.official_search_url && <p><a className="provider-link" href={selectedTransport.official_search_url} target="_blank" rel="noreferrer">Search trains on IRCTC ↗</a></p>}{selectedTransport?.includes_road_transfer && <p>Includes onward road transfer.</p>}</article>
          <article className="result-card"><h3>Hotel</h3><b>{selectedHotel?.name ?? "Hotel (name pending)"}</b>{selectedHotel?.address && <p>{selectedHotel.address}</p>}<p>{selectedHotel?.category ?? finalResponse.hotel.category ?? "Category pending"} · {selection.extras.room_split.length} rooms · {selection.extras.room_split.join(" + ")} guests</p>{selectedHotel?.price != null ? <p>{formatInr(finite(selectedHotel.price))}</p> : <QuoteChip status="pending" />}{selectedHotel && <p><a className="provider-link" href={bookingSearchUrl(finalResponse, selection.extras.room_split.length)} target="_blank" rel="noreferrer">Check current hotel rates ↗</a></p>}{finalResponse.hotel.cancellation_policy_required && <p><span className="warning-chip">Cancellation policy not verified</span></p>}</article>
          <article className="result-card timeline-card"><h3>Day-wise itinerary</h3><div className="timeline">{(finalResponse.final_plan.itinerary as JsonObject[]).map((day) => <section className="timeline-day" key={day.day}><b>Day {day.day}{day.date ? ` · ${day.date}` : ""}</b>{Array.isArray(day.places) && day.places.length > 0 ? <ul>{day.places.map((activity: JsonObject) => <li key={activity.id}>{activity.name}</li>)}</ul> : <p className="muted">Free day</p>}</section>)}</div></article>
          <article className="result-card"><h3>Weather</h3><p>{finalResponse.weather.summary ?? "Weather information unavailable."}</p><p>{finalResponse.weather.temp_range_c[0] == null || finalResponse.weather.temp_range_c[1] == null ? "Temperature range unavailable" : `${finalResponse.weather.temp_range_c[0]}–${finalResponse.weather.temp_range_c[1]} °C`}</p></article>
          <article className="result-card"><h3>Health tips</h3><p>{finalResponse.health.summary ?? "General travel guidance."}</p><ul>{finalResponse.health.considerations.map((tip) => <li key={tip}>{tip}</li>)}</ul><p>{finalResponse.health.medical_kit.join(" · ")}</p></article>
          <article className="result-card cost-summary"><h3>Cost summary</h3>{(costSummary.items as JsonObject[]).length ? <ul>{(costSummary.items as JsonObject[]).map((item, index) => <li key={`${item.item}-${index}`}>{item.item}: {formatInr(finite(item.amount))}</li>)}</ul> : <p>No priced items returned yet; unknown amounts are not counted as ₹0.</p>}<p>{costSummary.known_subtotal == null ? "Known subtotal: unavailable" : `Known subtotal: ${formatInr(finite(costSummary.known_subtotal))}`}</p><p>Selected total: {costSummary.selected_total == null ? <QuoteChip status="pending" /> : formatInr(finite(costSummary.selected_total))}</p><p>Budget: {formatInr(finalResponse.budget.min)}–{formatInr(finalResponse.budget.max)}</p><span className={`status-pill ${costSummary.within_limit === true ? "success" : costSummary.within_limit === false ? "failed" : "needs_review"}`}>{costSummary.within_limit === true ? "Within limit" : costSummary.within_limit === false ? "Over limit" : "Pending quotes"}</span></article>
        </div>
        <section className="open-items"><h3>Warnings and open items</h3>{pendingQuotes.length > 0 ? <><p>Pending quotes:</p><ul>{pendingQuotes.map((item) => <li key={item}>{item}</li>)}</ul></> : <p>No pending quotes.</p>}{[...new Set([...finalResponse.warnings, ...stringList(finalResponse.final_plan.warnings)])].map((warning) => <p className="result-warning" key={warning}>{warning}</p>)}{finalResponse.hotel.cancellation_policy_required && <p><span className="warning-chip">Hotel cancellation policy needs verification</span></p>}{nearestAirportTooFar && <p className="result-warning">Nearest airport is {finalResponse.feasibility.airport.distance_km} km away, beyond the {finalResponse.transport.airport_limit_km} km limit.</p>}</section>
        {confirmed && <p className="confirmed-note" role="status">Plan confirmed for review. No bookings have been made.</p>}
        <div className="final-actions"><button type="button" className="secondary-action" onClick={() => setScreen("builder")}>Back to edit</button><button type="button" onClick={() => setConfirmed(true)}>Confirm plan</button><button type="button" className="secondary-action" onClick={() => window.print()}>Download PDF / Print</button><button type="button" className="secondary-action" onClick={copyFinalJson}>{copied ? "Copied" : "Copy JSON"}</button></div>
        <details className="technical-details"><summary>Technical details</summary><div className="agents">{wf?.executions.map((execution) => <div className="agent" key={execution.id}><div><strong>{execution.agent_id}</strong><div className="agent-meta">{execution.stage} · attempt {execution.attempt}</div></div><span className={`badge ${execution.status}`}>{execution.status}</span></div>)}</div></details>
        <details className="json-details"><summary>View JSON</summary><pre>{JSON.stringify(finalResponse, null, 2)}</pre></details>
      </section>}
    </div>
  );
}

function formatInr(value: number | null): string {
  return value == null ? "—" : `INR ${value.toLocaleString("en-IN")}`;
}

function bookingSearchUrl(response: FinalResponse, rooms: number): string {
  const url = new URL("https://www.booking.com/searchresults.html");
  url.searchParams.set("ss", response.trip.to);
  url.searchParams.set("checkin", response.trip.start_date);
  url.searchParams.set("checkout", response.trip.end_date);
  url.searchParams.set("group_adults", String(response.traveler.adults));
  url.searchParams.set("group_children", String(response.traveler.children));
  url.searchParams.set("no_rooms", String(Math.max(1, rooms)));
  url.searchParams.set("selected_currency", "INR");
  return url.toString();
}

function QuoteChip({ status }: { status: "pending" | "available" }) {
  return <span className={`quote-chip ${status}`}>{status === "available" ? "Quote available" : "Pending quote"}</span>;
}
