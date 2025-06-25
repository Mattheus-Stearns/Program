import csv
import random
import json
from collections import defaultdict
import os
from datetime import datetime, timedelta

# TODO: Make an actual index.csv file

class ProgramSchedules:
    def __init__(self):
        self.index_data = {}  # key: ID, value: person info

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

                possible_days = [row['first option day'], row['second option day']]
                possible_nights = [row['first option night'], row['second option night']]

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

                # Track if either was unassigned in first pass
                if not day_off or not night_off:
                    unassigned_log.append({
                        'id': person_id,
                        'name': row['name'],
                        'email': row['personal email'],
                        'day_off': day_off or "Unassigned",
                        'night_off': night_off or "Unassigned",
                        'reason': "No available slots without coverage conflict or overcapacity"
                    })

                # Second pass fallback assignment (ignore coverage constraint)
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
    

    # TODO: currently coordinators.json is just filled with random data, actually cross reference it with the actual index.csv file to ensure that the id's are correct and legit
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

        # Determine who is unavailable each day due to their day off
        unavailable = defaultdict(set)  # day string -> set of staff IDs
        for staff_id, off_date_str in self.day_off_data.items():
            try:
                off_date = datetime.strptime(off_date_str, "%d/%m/%Y")
                missed_day = (off_date + timedelta(days=1)).strftime("%A")
                if missed_day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
                    unavailable[missed_day].add(staff_id)
            except:
                continue  # Skip malformed dates

        # Load coordinators.json
        with open(os.path.join("freetime_schedules", "coordinators.json")) as f:
            coordinator_data = json.load(f)  # location -> list of staff IDs

        # Load locations.json
        with open(os.path.join("freetime_schedules", "locations.json")) as f:
            locations = json.load(f)

        # Prepare output directory
        os.makedirs("freetime_schedules", exist_ok=True)

        # Identify certified groups
        lifeguards = {id for id, row in self.index_data.items() if row['lifeguard certification'].strip().lower() == 'yes'}
        archers = {id for id, row in self.index_data.items() if row['archery certification'].strip().lower() == 'yes'}
        climbers = {id for id, row in self.index_data.items() if row['high ropes certification'].strip().lower() == 'yes'}
        fishers = {id for id, row in self.index_data.items() if row.get('fishing proficiency', '').strip().lower() == 'yes'}

        # Track how often staff are assigned
        assignment_counts = defaultdict(int)

        schedule = {day: {} for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]}

        for day in schedule:
            assigned = set()
            lifeguard_pool = lifeguards - unavailable[day]

            # Step 1: Assign coordinators
            for location, ids in coordinator_data.items():
                for staff_id in ids:
                    if staff_id not in unavailable[day] and staff_id not in assigned:
                        schedule[day][location] = staff_id
                        assigned.add(staff_id)
                        assignment_counts[staff_id] += 1
                        break

            # Step 2: Assign at least 3 lifeguards
            lg_assigned = 0
            if "Lifeguard" not in schedule[day]:
                schedule[day]["Lifeguard"] = []
            for lg in sorted(lifeguard_pool, key=lambda x: assignment_counts[x]):
                if lg not in assigned:
                    schedule[day]["Lifeguard"].append(lg)
                    assigned.add(lg)
                    assignment_counts[lg] += 1
                    lg_assigned += 1
                    if lg_assigned >= 3:
                        break

            # Step 3: Assign remaining locations
            for location in locations:
                if location in schedule[day]:
                    continue  # Already assigned
                if location == "Lifeguard":
                    continue  # Already handled
                if location == "Archery" and day in ["Tuesday", "Thursday"]:
                    continue
                if location == "Climbing" and day in ["Tuesday", "Thursday"]:
                    continue

                # Determine eligible pool
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

                # Choose the least assigned available staff
                chosen = min(pool, key=lambda x: assignment_counts[x])
                schedule[day][location] = chosen
                assigned.add(chosen)
                assignment_counts[chosen] += 1

            # Fill more lifeguards only if other locations are filled
            if isinstance(schedule[day].get("Lifeguard"), list) and len(schedule[day]) >= len(locations) - 2:
                while len(schedule[day]["Lifeguard"]) < len(lifeguard_pool):
                    extra = [lg for lg in lifeguard_pool if lg not in assigned]
                    if not extra:
                        break
                    chosen = min(extra, key=lambda x: assignment_counts[x])
                    schedule[day]["Lifeguard"].append(chosen)
                    assigned.add(chosen)
                    assignment_counts[chosen] += 1

        # Write schedule files
        for day, loc_assignments in schedule.items():
            filename = os.path.join("freetime_schedules", f"{day.lower()}_schedule.csv")
            with open(filename, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Location", "Assigned_Staff_ID"])
                for location, staff in loc_assignments.items():
                    if isinstance(staff, list):
                        for s in staff:
                            writer.writerow([location, s])
                    else:
                        writer.writerow([location, staff])

        print("Freetime schedule files saved to freetime_schedules/ for Monday to Friday.")


def main():
    scheduler = ProgramSchedules()
    scheduler.assign_off_times()
    scheduler.assign_freetime_locations()

if __name__ == "__main__":
    main()