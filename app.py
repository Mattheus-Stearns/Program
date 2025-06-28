# TODO: currently coordinators.json is just filled with random data, actually cross reference it with the actual index.csv file to ensure that the id's are correct and legit
# TODO: Make an actual index.csv file
# TODO: Make use of dates.json

import csv
import random
import json
from collections import defaultdict
import os
from datetime import datetime, timedelta
import sys



class ProgramSchedules:
    def __init__(self, week_start_date):
        self.index_data = {}  # key: ID, value: person info
        self.day_off_data = {}
        self.week_start_date = datetime.strptime(week_start_date, "%d/%m/%Y")

    def assign_off_times(self):

        # Load index.csv
        with open("index.csv", newline='') as index_file:
            reader = csv.DictReader(index_file)
            for row in reader:
                self.index_data[row['id']] = row

        staff_ids = list(self.index_data.keys())
        staff_count = len(staff_ids)
        max_per_slot = max(1, int(staff_count * 0.25))

        # Read off_times_form.csv from off_schedules directory
        off_schedule_path = os.path.join("off_schedules", "off_times_form.csv")
        assignments = []
        unassigned_log = []

        used_day_slots = defaultdict(set)
        used_night_slots = defaultdict(set)
        assigned_day = {}
        assigned_night = {}

        with open(off_schedule_path, newline='') as off_file:
            reader = csv.DictReader(off_file)
            for row in reader:
                person_id = row['id']
                if person_id not in self.index_data:
                    continue

                coverage_id = self.index_data[person_id].get("coverage", "").strip()
                coverage_day = assigned_day.get(coverage_id)
                coverage_night = assigned_night.get(coverage_id)

                # Weighted shuffle of options
                def weighted_choice_order(first, second, weight_first=0.6):
                    return [first, second] if random.random() < weight_first else [second, first]

                possible_days = weighted_choice_order(row['first option day'], row['second option day'])
                possible_nights = weighted_choice_order(row['first option night'], row['second option night'])

                day_off = None
                for option in possible_days:
                    if len(used_day_slots[option]) < max_per_slot and coverage_day != option:
                        day_off = option
                        used_day_slots[option].add(person_id)
                        assigned_day[person_id] = day_off
                        break

                night_off = None
                for option in possible_nights:
                    if len(used_night_slots[option]) < max_per_slot and coverage_night != option:
                        night_off = option
                        used_night_slots[option].add(person_id)
                        assigned_night[person_id] = night_off
                        break

                if not day_off or not night_off:
                    unassigned_log.append({
                        'id': person_id,
                        'name': row['name'],
                        'email': row['personal email'],
                        'day_off': day_off or "Unassigned",
                        'night_off': night_off or "Unassigned",
                        'reason': "No available slots without coverage conflict or overcapacity"
                    })

                # Fallback ignoring coverage constraint
                if not day_off:
                    for option in possible_days:
                        if len(used_day_slots[option]) < max_per_slot:
                            day_off = option
                            used_day_slots[option].add(person_id)
                            assigned_day[person_id] = day_off
                            break
                    if not day_off:
                        day_off = "Unassigned"

                if not night_off:
                    for option in possible_nights:
                        if len(used_night_slots[option]) < max_per_slot:
                            night_off = option
                            used_night_slots[option].add(person_id)
                            assigned_night[person_id] = night_off
                            break
                    if not night_off:
                        night_off = "Unassigned"

                assignments.append({
                    'id': person_id,
                    'name': row['name'],
                    'email': row['personal email'],
                    'day_off': day_off,
                    'night_off': night_off,
                    'notes': row['notes']
                })

        # Write results.csv
        output_path = os.path.join("off_schedules", "results.csv")
        with open(output_path, mode='w', newline='') as result_file:
            fieldnames = ['id', 'name', 'email', 'day_off', 'night_off', 'notes']
            writer = csv.DictWriter(result_file, fieldnames=fieldnames)
            writer.writeheader()
            for entry in assignments:
                writer.writerow(entry)

        # Write unassigned log
        log_path = os.path.join("off_schedules", "unassigned_log.csv")
        with open(log_path, mode='w', newline='') as log_file:
            fieldnames = ['id', 'name', 'email', 'day_off', 'night_off', 'reason']
            writer = csv.DictWriter(log_file, fieldnames=fieldnames)
            writer.writeheader()
            for entry in unassigned_log:
                writer.writerow(entry)

        print(f"Assignment complete. Results saved to {output_path}")
        if unassigned_log:
            print(f"Some assignments required fallback. Details logged to {log_path}")    

    
    def assign_freetime_locations(self):

        # Load index.csv
        with open("index.csv", newline='') as index_file:
            reader = csv.DictReader(index_file)
            for row in reader:
                self.index_data[row['id']] = row

        # Load off_schedules/results.csv
        with open(os.path.join("off_schedules", "results.csv"), newline='') as off_file:
            reader = csv.DictReader(off_file)
            for row in reader:
                self.day_off_data[row['id']] = row['day_off']  # stored in DD/MM/YYYY

        # Prepare day name and date mapping for Monday-Friday only (5 days)
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        day_to_date = {}
        for i, day in enumerate(weekdays):
            date_str = (self.week_start_date + timedelta(days=i)).strftime("%d/%m/%Y")
            day_to_date[day] = date_str

        # Determine unavailable staff per freetime day (day after off start)
        unavailable = defaultdict(set)  # day -> set of staff IDs
        for staff_id, off_date_str in self.day_off_data.items():
            try:
                off_date = datetime.strptime(off_date_str, "%d/%m/%Y")
                missed_day = (off_date + timedelta(days=1)).strftime("%A")
                if missed_day in weekdays:
                    unavailable[missed_day].add(staff_id)
            except:
                continue  # skip malformed dates

        # Load coordinators.json and locations.json
        with open(os.path.join("freetime_schedules", "coordinators.json")) as f:
            coordinator_data = json.load(f)  # location -> list of staff IDs

        with open(os.path.join("freetime_schedules", "locations.json")) as f:
            locations = json.load(f)

        os.makedirs("freetime_schedules", exist_ok=True)

        # Identify certified groups
        lifeguards = {sid for sid, row in self.index_data.items() if row.get('lifeguard certification', '').strip().lower() == 'yes'}
        archers = {sid for sid, row in self.index_data.items() if row.get('archery certification', '').strip().lower() == 'yes'}
        climbers = {sid for sid, row in self.index_data.items() if row.get('high ropes certification', '').strip().lower() == 'yes'}
        fishers = {sid for sid, row in self.index_data.items() if row.get('fishing proficiency', '').strip().lower() == 'yes'}

        assignment_counts = defaultdict(int)
        schedule = {day: {} for day in weekdays}

        for day in weekdays:
            assigned = set()
            lifeguard_pool = lifeguards - unavailable[day]

            # Assign coordinators
            for location, ids in coordinator_data.items():
                for staff_id in ids:
                    if staff_id not in unavailable[day] and staff_id not in assigned:
                        schedule[day][location] = staff_id
                        assigned.add(staff_id)
                        assignment_counts[staff_id] += 1
                        break

            # Assign minimum 3 lifeguards
            if "Lifeguard" not in schedule[day]:
                schedule[day]["Lifeguard"] = []
            lg_assigned = 0
            for lg in sorted(lifeguard_pool, key=lambda x: assignment_counts[x]):
                if lg not in assigned:
                    schedule[day]["Lifeguard"].append(lg)
                    assigned.add(lg)
                    assignment_counts[lg] += 1
                    lg_assigned += 1
                    if lg_assigned >= 3:
                        break

            # Assign other locations
            for location in locations:
                if location in schedule[day]:
                    continue
                if location == "Lifeguard":
                    continue
                if location in ["Archery", "Climbing"] and day in ["Tuesday", "Thursday"]:
                    continue

                # Certification pools
                if location == "Archery":
                    pool = archers
                elif location == "Climbing":
                    pool = climbers
                elif location == "Fishing":
                    pool = fishers
                else:
                    pool = set(self.index_data.keys())

                pool = pool - assigned - unavailable[day]
                if not pool:
                    continue

                chosen = min(pool, key=lambda x: assignment_counts[x])
                schedule[day][location] = chosen
                assigned.add(chosen)
                assignment_counts[chosen] += 1

            # Add more lifeguards if all other locations are covered
            if isinstance(schedule[day].get("Lifeguard"), list) and len(schedule[day]) >= len(locations) - 2:
                while len(schedule[day]["Lifeguard"]) < 5:
                    extra = [lg for lg in lifeguard_pool if lg not in assigned]
                    if not extra:
                        break
                    chosen = min(extra, key=lambda x: assignment_counts[x])
                    schedule[day]["Lifeguard"].append(chosen)
                    assigned.add(chosen)
                    assignment_counts[chosen] += 1

            # Assign leftover staff to "Off"
            off_candidates = set(self.index_data.keys()) - assigned - unavailable[day]
            for staff_id in off_candidates:
                schedule[day].setdefault("Off", []).append(staff_id)
                assigned.add(staff_id)
                assignment_counts[staff_id] += 1

        # Write combined weekly schedule with date included
        consolidated_path = os.path.join("freetime_schedules", "weekly_schedule.csv")
        with open(consolidated_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Day", "Date", "Location", "Assigned_Staff_ID"])
            for day in weekdays:
                date = day_to_date[day]
                for location, staff in schedule[day].items():
                    if isinstance(staff, list):
                        for s in staff:
                            writer.writerow([day, date, location, s])
                    else:
                        writer.writerow([day, date, location, staff])
                # Also write staff who are off that day explicitly
                for staff_id in unavailable[day]:
                    writer.writerow([day, date, "Day Off", staff_id])

        print("Weekly freetime schedule saved to freetime_schedules/weekly_schedule.csv")


def get_next_monday(today=None):
    today = today or datetime.today()
    days_ahead = (7 - today.weekday()) % 7  # 0 = Monday
    days_ahead = 7 if days_ahead == 0 else days_ahead  # force next week if today is Monday
    next_monday = today + timedelta(days=days_ahead)
    return next_monday.strftime("%d/%m/%Y")

def main():
    if len(sys.argv) > 1:
        try:
            week_start_date = datetime.strptime(sys.argv[1], "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            print("Error: Date must be in format DD/MM/YYYY")
            sys.exit(1)
    else:
        week_start_date = get_next_monday()

    scheduler = ProgramSchedules(week_start_date)
    scheduler.assign_off_times()
    scheduler.assign_freetime_locations()

if __name__ == "__main__":
    main()