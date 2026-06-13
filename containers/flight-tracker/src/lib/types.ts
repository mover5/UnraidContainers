// A clock time stored as "HH:MM" (24h, local to the relevant airport), or null.
export type ClockTime = string | null;

export interface Flight {
  id: string;
  date: string; // yyyy-mm-dd
  passengers: string;
  carrier: string;
  flight_number: string;
  origin: string;
  destination: string;
  scheduled_departure: ClockTime;
  delayed_departure: ClockTime;
  gate_push: ClockTime;
  takeoff: ClockTime;
  scheduled_arrival: ClockTime;
  delayed_arrival: ClockTime;
  land: ClockTime;
  gate_arrive: ClockTime;
  tz_change: number; // hours; positive = destination ahead of origin
  projected_flying_time: string | null;
  deicing: boolean;
  gate_occupied: boolean | null;
  notes: string | null; // legacy single note carried over from the sheet
}

export interface FlightNote {
  id: string;
  flight_id: string;
  body: string;
  created_at: string; // ISO timestamp
}

// The four taggable in-flight events, in chronological order.
export const EVENT_FIELDS = [
  { key: 'gate_push', label: 'Gate Push', short: 'Push' },
  { key: 'takeoff', label: 'Takeoff', short: 'Takeoff' },
  { key: 'land', label: 'Land', short: 'Land' },
  { key: 'gate_arrive', label: 'Gate Arrive', short: 'Arrive' },
] as const;

export type EventKey = (typeof EVENT_FIELDS)[number]['key'];

export type NewFlight = Omit<Flight, 'id'>;
