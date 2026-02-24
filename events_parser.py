# -*- coding: utf-8 -*-
"""
Created on Fri Feb 20 14:58:09 2026

@author: Admin
"""

# -*- coding: utf-8 -*-
"""
events_parser.py

Streams output_events.xml(.gz) and reconstructs, for each car vehicle:
  - A list of Trip objects: t_start, t_end, distance_m, from_link, to_link
  - A person -> vehicle mapping

Requires: link_length dict from network_parser.build_length_lookup()
"""

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional


# ── Data containers ────────────────────────────────────────────────────────

@dataclass
class Trip:
    person_id:  str     # who was driving
    vehicle_id: str     # which car
    t_start:    float   # when the trip started, in seconds from midnight
    t_end:      float   # when it ended, in seconds from midnight
    distance_m: float   # total metres driven during this trip
    from_link:  str     # the link where the car entered traffic
    to_link:    str     # the link where the car left traffic


@dataclass
class ActivityEvent:
    person_id: str
    act_type:  str      # "home", "work", "leisure", etc.
    link_id:   str      # where the person was parked
    t_start:   float    # when they arrived
    t_end:     float    # when they left


# This is a temporary container for a trip that has started but not yet finished. 
# It lives in open_trips until a VehicleLeavesTraffic event converts it into a proper Trip

@dataclass
class _OpenTrip:        #The underscore _ at the start is a Python convention meaning "private — only used inside this file"
    person_id:  str
    vehicle_id: str
    t_start:    float
    from_link:  str
    distance_m: float = 0.0  # accumulated as LinkEnter events arrive
    current_link: str = ""


# ── Main parser ────────────────────────────────────────────────────────────

def parse_events(
    events_path: str,
    link_length: dict[str, float],      # comes from Step 1 (network_parser.py)
    car_vehicles: Optional[set[str]] = None,  # car_vehicles is optional: if you pass a set of known car vehicle IDs, only those are processed. If you pass nothing (None), all vehicles are processed. This is useful if you want to pre-filter only EVs
) -> tuple[list[Trip], list[ActivityEvent], dict[str, str]]:    # Returns three things: the trips list, the activities list, and the person→vehicle mapping
    
    """
    Streams output_events.xml(.gz) and extracts:
      - trips      : list[Trip]          one entry per completed car trip
      - activities : list[ActivityEvent] one entry per completed activity
      - person_to_vehicle : dict[person_id -> vehicle_id]

    Args:
        events_path   : path to output_events.xml or output_events.xml.gz
        link_length   : dict from network_parser.build_length_lookup()
        car_vehicles  : optional set of vehicle IDs to keep (filters out PT/bikes)

    Returns:
        trips, activities, person_to_vehicle
    """

    # Running state: vehicles currently on a trip
    # Private cars
    open_trips:    dict[str, _OpenTrip] = {}
    # key = vehicle_id
    # A vehicle enters this dict on VehicleEntersTraffic and leaves it on VehicleLeavesTraffic

    # Running state: persons currently doing an activity
    open_activities: dict[str, tuple[str, str, float]] = {}
    # key   = person_id
    # value = (act_type, link_id, t_start)
    # A person enters this dict on actstart and leaves it on actend

    """
    These are the "memory" of the parser. 
    At any point during streaming, open_trips contains all vehicles currently on a trip.
    Similarly, open_activities contains all persons currently doing an activity.
    """
    

    # Results
    trips:      list[Trip]          = []       # private car trips
    activities: list[ActivityEvent] = []

    # Person <-> vehicle mapping (built from PersonEntersVehicle events)
    person_to_vehicle: dict[str, str] = {}      # private car
    vehicle_to_person: dict[str, str] = {}

    opener = gzip.open if events_path.endswith(".gz") else open

    with opener(events_path, "rb") as f:
        for _, elem in ET.iterparse(f, events=("start",)):  
            # Note the _ instead of event as the first variable — this is a Python convention meaning "I know this variable exists but I don't need it". 
            # We always use events=("start",) so it would always be "start" anyway, so we discard it

            # We only care about <event> tags, skip everything else
            if elem.tag != "event":
                elem.clear()
                continue

            event_type = elem.attrib.get("type", "")
            time       = float(elem.attrib.get("time", 0)) #Converts the string into float

            # ── 1. Person boards a vehicle ─────────────────────────────
            if event_type == "PersonEntersVehicle":
                person_id  = elem.attrib["person"]
                vehicle_id = elem.attrib["vehicle"]

                # Only process car vehicles (format: "personId:car")

                if vehicle_id.endswith(":car"):
                    # Only record the FIRST person (the driver), ignore passengers
                    if vehicle_id not in vehicle_to_person:
                        person_to_vehicle[person_id]  = vehicle_id  # These are needed to link the vehicle to the person
                        vehicle_to_person[vehicle_id] = person_id   # So that later on we can link the activity of the person to the vehicle


            # ── 2. Vehicle enters traffic (trip starts) ────────────────
            elif event_type == "vehicle enters traffic":
                vehicle_id = elem.attrib["vehicle"]
                link_id = elem.attrib["link"]
                
                # Skip non-car vehicles entirely
                if not vehicle_id.endswith(":car"):
                    elem.clear()
                    continue
                
                # Skip if not in the optional filter set
                if car_vehicles and vehicle_id not in car_vehicles:
                    elem.clear()
                    continue
                
                person_id = vehicle_to_person.get(vehicle_id, vehicle_id)
                
                # vehicle_to_person.get(vehicle_id, vehicle_id):
                # Try to find the driver's person_id from the mapping built in Block 1
                # If not found (edge case: VehicleEntersTraffic fired before PersonEntersVehicle)
                # fall back to using vehicle_id itself — better than crashing

                open_trips[vehicle_id] = _OpenTrip(
                    person_id=person_id,
                    vehicle_id=vehicle_id,
                    t_start=time,
                    from_link=link_id,
                    current_link=link_id,
                )

            # ── 3. Vehicle enters a link (accumulate distance) ─────────
            elif event_type == "entered link":
                vehicle_id = elem.attrib.get("vehicle")
                link_id    = elem.attrib.get("link")
                

                # Guard against missing attributes (e.g. pedestrian events)
                if vehicle_id is None or link_id is None:
                    elem.clear()
                    continue

                if vehicle_id in open_trips and link_id in link_length:
                    open_trips[vehicle_id].distance_m   += link_length[link_id]
                    open_trips[vehicle_id].current_link  = link_id


            # ── 4. Vehicle leaves traffic (trip ends) ──────────────────
            elif event_type == "vehicle leaves traffic":
                vehicle_id = elem.attrib["vehicle"]
                link_id    = elem.attrib["link"]

                if vehicle_id in open_trips:
                    ot = open_trips.pop(vehicle_id)
                    trips.append(Trip(
                        person_id=ot.person_id,
                        vehicle_id=vehicle_id,
                        t_start=ot.t_start,
                        t_end=time,
                        distance_m=ot.distance_m,
                        from_link=ot.from_link,
                        to_link=link_id,
                    ))


            
            # ── 5. Activity starts ─────────────────────────────────────       
            # These activities are only the interactions with the cehicle. 
            # The real activities have to be implemented
            elif event_type == "actstart":
                person_id = elem.attrib["person"]
                act_type  = elem.attrib.get("actType", "unknown")
                link_id   = elem.attrib.get("link", "unknown")
                open_activities[person_id] = (act_type, link_id, time)

            # ── 6. Activity ends ───────────────────────────────────────
            # These activities are only the interactions with the cehicle. 
            # The real activities have to be implemented
            elif event_type == "actend":
                person_id = elem.attrib["person"]
                link_id   = elem.attrib.get("link", "unknown")
                act_type  = elem.attrib.get("actType", "unknown")

                if person_id in open_activities:
                    prev_act_type, prev_link, t_act_start = open_activities.pop(person_id)
                    activities.append(ActivityEvent(
                        person_id=person_id,
                        act_type=prev_act_type,
                        link_id=prev_link,
                        t_start=t_act_start,
                        t_end=time,
                    ))

            elem.clear()

    # ── Stuck agents warning ───────────────────────────────────────────────
    if open_trips:
        print(f"  ⚠ {len(open_trips)} vehicles had unclosed trips (stuck agents), discarded.")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"[Private] Parsed {len(trips):,} trips | "
          f"Unique vehicles: {len({t.vehicle_id for t in trips}):,} | "
          f"Unique persons: {len(person_to_vehicle):,}")
    print(f"[Both]    Parsed {len(activities):,} activities.")

    return trips, activities, person_to_vehicle
