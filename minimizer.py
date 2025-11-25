#!/usr/bin/env python3
#
# Add advocates, a year and see where they should meet next.
#

import requests
import geopy.distance
from geopy.geocoders import Nominatim
from datetime import datetime
import json
import time
import argparse
from functools import lru_cache

@lru_cache(maxsize=None)
def get_coordinates(city, country):
    try:
        geolocator = Nominatim(user_agent="EventSorter2", timeout=2)
        location = geolocator.geocode(f"{city}, {country}")
        time.sleep(1.2)
        if location:
            return (location.latitude, location.longitude)
        else:
            print(f"Warning: Could not geocode '{city}, {country}'. Location will be skipped.")
            return None
    except Exception as e:
        print(f"An error occurred during geocoding for {city}, {country}: {e}")
        return None

def calculate_distance(coords1, coords2):
    if coords1 and coords2:
        return geopy.distance.geodesic(coords1, coords2).km
    return float('inf')

def enrich_advocates_with_coords(advcoates):
    for advocate in advocates:
        coords = get_coordinates(advocate['city'], advocate['country'])
        if coords:
            advocate['coords']= coords
        else:
            print(f"XX IGNORING '{advocate['name']}', NO LOCATION FOR '{advocate['city']},{advocate['country']}'.")

def filter_events_by_years_and_excludes(input_events, years, excludes):
    events = []
    for year in years:
        events += list(filter(lambda e: datetime.fromtimestamp(int(e['date'][0])/ 1000).year == year, input_events))

    for exclude in excludes:
        if exclude.strip():
            events = list(filter(lambda e: exclude.upper() not in str(e).upper(), events))

    return events

def find_best_events(years, advocates, excludes, maximum):
    print(f"Found {len(advocates)} advocates.")
    print("Geocoding advocate locations…")
    enrich_advocates_with_coords(advocates)

    print("Fetching event data…")
    try:
        response = requests.get("https://developers.events/all-events.json")
        response.raise_for_status()
        events = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: Could not fetch event data. {e}")
        return

    events = filter_events_by_years_and_excludes(events, years, excludes)
    print(f"Processing {len(events)} events for the year(s) {years} …")

    events_with_distances = []
    for i, event in enumerate(events):
        print(f"{i+1: 5d} / {len(events)}({int((float(i)/len(events))*100) :02d}%): ", end="")
        
        try:
            print(event['name'], end=': ')
            event_city = event.get('city')
            event_country = event.get('country')

            if not event_city or not event_country:
                print()
                continue

            event_coords = get_coordinates(event_city, event_country)
            if not event_coords:
                print()
                continue

            total_distance = 0
            individual_distances = []
            for advocate in advocates:
                distance = calculate_distance(advocate['coords'], event_coords)
                total_distance += distance
                individual_distances.append({'name': advocate['name'], 'distance': distance})

            if total_distance != float('inf'):
                events_with_distances.append({
                    'name': event.get('name'),
                    'city': event_city,
                    'link': event.get('hyperlink'),
                    'country': event_country,
                    'total_distance': total_distance,
                    'individual_distances': individual_distances,
                    'meta': event,
                })
            print(total_distance)
        except (ValueError, TypeError) as e:
            # skip events with malformed data
            print(event)
            print(e)
            continue

    if not events_with_distances:
        print(f"No valid events found for the years {years}.")
        return

    sorted_events = sorted(events_with_distances, key=lambda x: x['total_distance'])

    print(f"\n--- Top {maximum} conferences for {" ".join(map(lambda y: str(y), years))} to minimize travel distance ---")
    print(f"(excluding {" and ".join(excludes)})\n")

    for i, event in enumerate(sorted_events[:maximum]):
        print(f"{i+1}. {event['name']}")
        print(f"   Location: {event['city']}, {event['country']}")
        print(f"   Date: {datetime.fromtimestamp(event['meta']['date'][0]/1000)}")
        print(f"   Link: {event['link']}")
        print(f"   ∑ Travel: {event['total_distance']:,.0f} km")
        for dist in event['individual_distances']:
            print(f"     - {dist['name']:10s}: {dist['distance']:,.0f} km ({dist['distance'] * 0.6213712:,.0f} mi)")
        print("-" * 30)

def advocates_arg_to_list(advocates):
    result = []
    for advocate in advocates.split(','):
        name, city, country = advocate.split(":")
        result += [{'name':name,'city':city,'country':country}]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Find developer events that minimize team travel distance.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
            "--years", 
            type=str, 
            required=True, 
            help="The year(s) to search for events (e.g., 2024). Comma separated."
        )

    parser.add_argument(
        "--advocates",
        type=str,
        required=True,
        help="A string of advocates and their locations. Example 'Peter:Mainz:Germany,Hans:London:Ontario'."
    )
    
    parser.add_argument(
            "--excludes", 
            type=str, 
            required=False, 
            default="", 
            help="Comma seperated list of words to exclude from matching events."
        )

    parser.add_argument(
            "--max",
            type=int,
            required=False,
            default=10,
            help="Maximum amount of sorted events returned."
        )

    args = parser.parse_args()

    years = list(map(lambda y: int(y.strip()), args.years.split(',')))

    advocates = advocates_arg_to_list(args.advocates)

    excludes = args.excludes.split(',')

    find_best_events(years, advocates, excludes, args.max)

