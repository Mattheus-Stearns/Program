# TODO: Automatically assign time off if unassigned (is it )
# TODO: Add one off period / max of two per skills class for staff
# TODO: Maybe add to a web app?
# TODO: Make sure id is connected end to end thru email across index and off_times_form
# TODO: Make sure that campers get assigned to things that they are assigned to & getting assigned to unique skills classes
import os
import csv
import random
import json
from collections import defaultdict
from datetime import datetime, timedelta
import pandas as pd
import importlib.resources

class ProgramSchedules:
    def __init__(self, week_start_date):
        self.index_data = {}
        self.day_off_data = {}
        self.week_start_date = datetime.strptime(week_start_date, "%d/%m/%Y")
        self.skills_schedule = {}
        self.skills_by_staff = {}
        
        # Get paths to data files (updated approach)
        with importlib.resources.path('camp_scheduler', 'data') as data_path:
            self.data_dir = str(data_path)
        
        self.index_path = os.path.join(self.data_dir, "index.csv")
        self.staff_info = pd.read_csv(self.index_path)
        
        # Create output directory
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.output_dir = os.path.join("Output", self.timestamp)
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_data_path(self, filename):
        """Helper to get paths to data files"""
        return os.path.join(self.data_dir, filename)

    def _write_output(self, filename, content, mode='w'):
        """Helper to write output files directly to output directory"""
        path = os.path.join(self.output_dir, filename)
        if isinstance(content, pd.DataFrame):
            content.to_csv(path, index=False)
        elif isinstance(content, (list, dict)):
            with open(path, mode, newline='') as f:
                if filename.endswith('.csv'):
                    writer = csv.writer(f)
                    writer.writerows(content)
                else:
                    json.dump(content, f, indent=2)
        else:
            with open(path, mode) as f:
                f.write(content)
        return path

    def assign_off_times(self):
        try:
            # Load blackout periods from dates.json
            with open(self._get_data_path("dates.json")) as f:
                dates_config = json.load(f)
            
            # Convert blackout periods to datetime objects with 1-day buffer
            blackout_periods = []
            for period in dates_config["blackout_periods"].values():
                start_date = datetime.strptime(period["start"], "%Y-%m-%d") - timedelta(days=1)
                end_date = datetime.strptime(period["end"], "%Y-%m-%d") + timedelta(days=1)
                blackout_periods.append((start_date, end_date))
            
            def is_blackout_date(date_str):
                try:
                    date = datetime.strptime(date_str, "%d/%m/%Y")
                    for start, end in blackout_periods:
                        if start <= date <= end:
                            return True
                    return False
                except ValueError:
                    return True  # Treat invalid dates as blackout

            def is_consecutive_daynight(day_str, night_str):
                try:
                    day_date = datetime.strptime(day_str, "%d/%m/%Y")
                    night_date = datetime.strptime(night_str, "%d/%m/%Y")
                    return night_date == day_date + timedelta(days=1)
                except:
                    return False

            # Load staff data
            with open(self.index_path, newline='') as index_file:
                reader = csv.DictReader(index_file)
                for row in reader:
                    self.index_data[row['id']] = row

            staff_ids = list(self.index_data.keys())
            staff_count = len(staff_ids)
            max_per_slot = max(1, int(staff_count * 0.25))

            # Read time off requests
            off_schedule_path = self._get_data_path("off_times_form.csv")
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

                    # Process day off options (filter blackouts)
                    day_options = []
                    for day in [row['first option day'], row['second option day']]:
                        if day and not is_blackout_date(day):
                            day_options.append(day)
                    
                    # Process night off options (filter blackouts)
                    night_options = []
                    for night in [row['first option night'], row['second option night']]:
                        if night and not is_blackout_date(night):
                            night_options.append(night)

                    # Skip if no valid options
                    if not day_options or not night_options:
                        unassigned_log.append({
                            'id': person_id,
                            'name': row['name'],
                            'email': row['personal email'],
                            'day_off': "Unassigned",
                            'night_off': "Unassigned",
                            'reason': "All preferred dates in blackout periods"
                        })
                        continue

                    # Assign day off (try both options)
                    day_off = None
                    for option in day_options:
                        if len(used_day_slots[option]) < max_per_slot:
                            day_off = option
                            used_day_slots[option].add(person_id)
                            assigned_day[person_id] = day_off
                            break

                    # Assign night off (with consecutive check)
                    night_off = None
                    for option in night_options:
                        # Check if this night off would be consecutive to day off
                        if day_off and is_consecutive_daynight(day_off, option):
                            continue  # Skip this night option
                            
                        if len(used_night_slots[option]) < max_per_slot:
                            night_off = option
                            used_night_slots[option].add(person_id)
                            assigned_night[person_id] = night_off
                            break

                    # Handle unassigned cases
                    if not day_off or not night_off:
                        reason = "No available slots"
                        if day_off and not night_off:
                            reason = "No valid night off (would be consecutive to day off)"
                        
                        unassigned_log.append({
                            'id': person_id,
                            'name': row['name'],
                            'email': row['personal email'],
                            'day_off': day_off or "Unassigned",
                            'night_off': night_off or "Unassigned",
                            'reason': reason
                        })

                    # Add to final assignments
                    assignments.append({
                        'id': person_id,
                        'name': row['name'],
                        'email': row['personal email'],
                        'day_off': day_off or "Unassigned",
                        'night_off': night_off or "Unassigned",
                        'notes': row.get('notes', '')
                    })

            # Write outputs
            results_path = os.path.join(self.output_dir, "day_off_results.csv")
            pd.DataFrame(assignments or [{
                'id': '', 'name': '', 'email': '', 
                'day_off': '', 'night_off': '', 'notes': ''
            }]).to_csv(results_path, index=False)
            
            unassigned_path = os.path.join(self.output_dir, "day_off_unassigned.csv")
            pd.DataFrame(unassigned_log or [{
                'id': '', 'name': '', 'email': '',
                'day_off': '', 'night_off': '', 'reason': 'No assignments generated'
            }]).to_csv(unassigned_path, index=False)
            
            if not assignments:
                print("Warning: No valid assignments generated - using empty template")
            return assignments
        
        except Exception as e:
            print(f"Error in assign_off_times: {str(e)}")
            # Create empty files to prevent downstream errors
            empty_df = pd.DataFrame(columns=[
                'id', 'name', 'email', 'day_off', 'night_off', 'notes'
            ])
            empty_df.to_csv(os.path.join(self.output_dir, "day_off_results.csv"), index=False)
            return []

    def assign_freetime_locations(self):
        try:
            # Load index.csv
            with open(self.index_path, newline='') as index_file:
                reader = csv.DictReader(index_file)
                for row in reader:
                    self.index_data[row['id']] = row

            # Load off_schedules/results.csv from output
            off_results_path = os.path.join(self.output_dir, "day_off_results.csv")
        
            if not os.path.exists(off_results_path):
                raise FileNotFoundError("day_off_results.csv not found")
                
            with open(off_results_path, newline='') as off_file:
                reader = csv.DictReader(off_file)
                
                # Check if file is empty
                if not reader.fieldnames:
                    print("Warning: Empty day off results - using default values")
                    self.day_off_data = {}
                    return
                    
                self.day_off_data = {
                    row['id']: row['day_off']
                    for row in reader 
                    if row.get('id') and row.get('day_off')
                }

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

            # Load coordinators.json and locations.json from data directory
            with open(self._get_data_path("coordinators.json")) as f:
                coordinator_data = json.load(f)

            with open(self._get_data_path("locations.json")) as f:
                locations = json.load(f)

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
                    if location in schedule[day] or location == "Lifeguard":
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

                    # Apply department restriction
                    restricted_departments = {"Mad City", "Chippe", "Tamakwa"}
                    if location in restricted_departments:
                        pool = {sid for sid in pool if self.index_data[sid].get("department", "").strip() == location}

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

            # Prepare output data
            output_rows = []
            for day in weekdays:
                date = day_to_date[day]
                for location, staff in schedule[day].items():
                    if isinstance(staff, list):
                        for s in staff:
                            output_rows.append([day, date, location, s])
                    else:
                        output_rows.append([day, date, location, staff])
                # Also write staff who are off that day explicitly
                for staff_id in unavailable[day]:
                    output_rows.append([day, date, "Day Off", staff_id])

            # Write directly to output
            freetime_path = self._write_output("freetime_schedule.csv", 
                [["Day", "Date", "Location", "Assigned_Staff_ID"]] + output_rows)

            print(f"Weekly freetime schedule saved to {freetime_path}")

        except Exception as e:
            print(f"Error loading day off results: {str(e)}")
            self.day_off_data = {}  # Fallback to empty data

    def load_staff_info(self, index_path=None):
        path = index_path if index_path else self.index_path
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                staff_id = int(row["id"])
                self.staff_info[staff_id] = {
                    "email": row["personal email"],
                    "name": row["name"],
                    "lifeguard": row["lifeguard certification"].strip().lower() == "yes",
                    "archery": row["archery certification"].strip().lower() == "yes",
                    "high_ropes": row["high ropes certification"].strip().lower() == "yes",
                    "fishing": row["fishing proficiency"].strip().lower() == "yes"
                }

    def generate_coverage_schedule(self, staff_skills_schedule, days_off_schedule, staff_data):
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        periods = [1, 2, 3]
        coverage_schedule = defaultdict(lambda: defaultdict(lambda: None))

        off_by_day_period = defaultdict(list)
        for staff_id, day_periods in days_off_schedule.items():
            for day, periods_off in day_periods.items():
                for period in periods_off:
                    off_by_day_period[(day, period)].append(int(staff_id))

        for (day, period), off_staff_ids in off_by_day_period.items():
            for off_id in off_staff_ids:
                available_staff = []
                for candidate_id in staff_data:
                    if candidate_id == off_id:
                        continue
                    if day in days_off_schedule.get(str(candidate_id), {}) and period in days_off_schedule[str(candidate_id)][day]:
                        continue
                    assignment = staff_skills_schedule.get(candidate_id, {}).get(day, {}).get(period)
                    if assignment and assignment['class'] not in ['Unassigned', 'OFF']:
                        continue
                    available_staff.append(candidate_id)

                if available_staff:
                    assigned_cover = available_staff[0]
                    coverage_schedule[assigned_cover][f"{day} P{period}"] = f"Cover for {off_id}"
                else:
                    print(f"[Warning] No available staff to cover {off_id} during {day} P{period}")

        return coverage_schedule

    def assign_skills_classes(self):
        # Load required data from package data directory
        with open(self._get_data_path("classes.json")) as f:
            class_configs = json.load(f)
        with open(self._get_data_path("fixed_skills_off.json")) as f:
            fixed_off_periods = json.load(f)

        staff_data = pd.read_csv(self.index_path)
        staff_data = staff_data.set_index("id").to_dict("index")

        staff_daily_schedule = defaultdict(lambda: defaultdict(dict))
        class_assignments = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        class_capacity = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        unassigned_log = []

        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        periods = [1, 2, 3]

        # First assign coordinators and fixed offs
        for class_name, config in class_configs.items():
            for coord_id in config["coordinators"]:
                for day in weekdays:
                    for period in config["preferred_periods"]:
                        if config.get("double_period") and period == 3:
                            continue
                        assigned = False
                        if coord_id in staff_daily_schedule:
                            if day in staff_daily_schedule[coord_id] and period in staff_daily_schedule[coord_id][day]:
                                continue
                        if class_capacity[class_name][day][period] < config["staff_required"]:
                            staff_daily_schedule[coord_id][day][period] = {"class": class_name, "role": "lead"}
                            class_assignments[day][period][class_name].append((coord_id, "lead"))
                            class_capacity[class_name][day][period] += 1
                            assigned = True
                        if assigned:
                            break

        for staff_id, day_periods in fixed_off_periods.items():
            for day, periods_off in day_periods.items():
                for period in periods_off:
                    staff_daily_schedule[int(staff_id)][day][period] = {"class": "OFF", "role": "none"}

        # Assign remaining classes
        for day in weekdays:
            for period in periods:
                for class_name, config in class_configs.items():
                    if period not in config["preferred_periods"]:
                        continue
                    if config.get("double_period") and period == 3:
                        continue
                    needed = config["staff_required"] - class_capacity[class_name][day][period]
                    if needed <= 0:
                        continue
                    eligible_staff = []
                    for staff_id, info in staff_data.items():
                        if staff_id in config.get("coordinators", []):
                            continue
                        if day in staff_daily_schedule[staff_id] and period in staff_daily_schedule[staff_id][day]:
                            continue
                        if config.get("double_period") and ((period + 1) in staff_daily_schedule[staff_id][day]):
                            continue

                        if class_name == "Waterfront" and info["lifeguard certification"] != "Yes":
                            continue
                        if class_name == "Archery" and info["archery certification"] != "Yes":
                            continue
                        if class_name == "High Ropes" and info["high ropes certification"] != "Yes":
                            continue
                        if class_name == "Fishing" and info["fishing proficiency"] != "Yes":
                            continue

                        eligible_staff.append(staff_id)

                    for i in range(min(needed, len(eligible_staff))):
                        sid = eligible_staff[i]
                        role = "assistant"
                        if class_name == "Fishing" and info["fishing proficiency"] == "Yes":
                            role = "lead"
                        staff_daily_schedule[sid][day][period] = {"class": class_name, "role": role}
                        class_assignments[day][period][class_name].append((sid, role))
                        class_capacity[class_name][day][period] += 1
                        if config.get("double_period"):
                            staff_daily_schedule[sid][day][period + 1] = {"class": class_name, "role": role}

        # Track unassigned periods
        for staff_id in staff_data:
            for day in weekdays:
                for period in periods:
                    if period not in staff_daily_schedule[staff_id][day]:
                        staff_daily_schedule[staff_id][day][period] = {"class": "OFF", "role": "none"}
                        unassigned_log.append({"id": staff_id, "day": day, "period": period})

        # Prepare skills schedule output
        skills_output = []
        header = ["id"] + [f"{day} P{p}" for day in weekdays for p in periods]
        skills_output.append(header)
        for staff_id in staff_data:
            row = [staff_id]
            for day in weekdays:
                for p in periods:
                    entry = staff_daily_schedule[staff_id][day][p]
                    if entry["class"] == "OFF":
                        row.append("OFF")
                    elif entry["role"] == "lead":
                        row.append(f"Lead {entry['class']}")
                    elif entry["role"] == "assistant":
                        row.append(f"Assistant {entry['class']}")
                    else:
                        row.append("Unassigned")
            skills_output.append(row)

        # Write skills schedule directly to output
        skills_path = self._write_output("skills_schedule.csv", skills_output)

        # Write unassigned log
        unassigned_path = self._write_output("skills_unassigned.csv", 
            [["id", "day", "period"]] + [[x["id"], x["day"], x["period"]] for x in unassigned_log])

        self.skills_schedule = class_assignments
        self.skills_by_staff = staff_daily_schedule
        
        # Generate coverage schedule
        coverage_schedule = self.generate_coverage_schedule(staff_daily_schedule, fixed_off_periods, staff_data)

        # Prepare coverage output
        coverage_output = []
        coverage_header = ["id"] + [f"{day} P{p}" for day in weekdays for p in periods]
        coverage_output.append(coverage_header)
        for staff_id in staff_data:
            row = [staff_id]
            for day in weekdays:
                for p in periods:
                    task = coverage_schedule[staff_id].get(f"{day} P{p}", "")
                    row.append(task if task else "")
            coverage_output.append(row)

        # Write coverage schedule
        coverage_path = self._write_output("coverage_schedule.csv", coverage_output)

        print(f"Weekly skills classes schedule saved to {skills_path}")
        print(f"Coverage skills classes schedule saved to {coverage_path}")

    def assign_campers_to_skills(self):
        # Load class configurations from package data directory
        with open(self._get_data_path("classes.json")) as f:
            class_configs = json.load(f)

        # Load camper choices
        campers = []
        with open(self._get_data_path("camper_choices.csv")) as f:
            reader = csv.DictReader(f)
            for row in reader:
                campers.append(row)

        # Build demand list with weights
        class_demand = defaultdict(list)  # class -> list of (weight, camper_id, camper_data)
        for camper in campers:
            for i in range(1, 6):
                choice = camper[f'class{i}']
                if choice:
                    class_demand[choice].append((i, camper['id'], camper))

        # Sort demand FIFO style with preference weighting
        for class_name in class_demand:
            class_demand[class_name].sort(key=lambda x: (x[0], int(x[1])))

        # Assignments and tracking
        camper_assignments = defaultdict(dict)  # camper_id -> period -> class
        class_rosters = defaultdict(lambda: defaultdict(list))  # class -> period -> list of camper ids
        unassignable_campers = []
        inactive_classes = set()

        # Track assigned periods per camper
        camper_periods = defaultdict(set)

        # First pass: assign up to 3 periods
        for priority in range(1, 6):
            for class_name, demand_list in class_demand.items():
                config = class_configs.get(class_name, {})
                preferred_periods = config.get("preferred_periods", [])
                is_double = config.get("double_period", False)

                for weight, camper_id, camper in demand_list:
                    if weight != priority:
                        continue
                    if camper_id in camper_assignments and len(camper_assignments[camper_id]) >= 3:
                        continue

                    # Find a compatible period
                    assigned = False
                    for p in sorted(preferred_periods):
                        if is_double:
                            if p == 3:
                                if 3 not in camper_periods[camper_id]:
                                    camper_assignments[camper_id][p] = class_name
                                    camper_periods[camper_id].add(3)
                                    class_rosters[class_name][p].append(camper_id)
                                    assigned = True
                                    break
                            elif p in [1, 2]:
                                if p not in camper_periods[camper_id] and (p + 1) not in camper_periods[camper_id]:
                                    camper_assignments[camper_id][p] = class_name
                                    camper_assignments[camper_id][p + 1] = class_name
                                    camper_periods[camper_id].add(p)
                                    camper_periods[camper_id].add(p + 1)
                                    class_rosters[class_name][p].append(camper_id)
                                    assigned = True
                                    break
                        else:
                            if p not in camper_periods[camper_id]:
                                camper_assignments[camper_id][p] = class_name
                                camper_periods[camper_id].add(p)
                                class_rosters[class_name][p].append(camper_id)
                                assigned = True
                                break
                    if assigned and len(camper_assignments[camper_id]) >= 3:
                        break

        # Identify underfilled classes
        for class_name, period_map in class_rosters.items():
            for period, roster in period_map.items():
                staff_count = class_configs[class_name]["staff_required"]
                if len(roster) < 4 * staff_count:
                    inactive_classes.add((class_name, period))

        # Reassign campers from inactive classes
        for camper in campers:
            camper_id = camper['id']
            periods_to_remove = []
            for period, cname in camper_assignments[camper_id].items():
                if (cname, period) in inactive_classes:
                    periods_to_remove.append(period)
            for period in periods_to_remove:
                del camper_assignments[camper_id][period]
                camper_periods[camper_id].discard(period)

        # Try to refill missing periods for affected campers
        for camper in campers:
            camper_id = camper['id']
            if len(camper_assignments[camper_id]) >= 3:
                continue
            for i in range(1, 6):
                cname = camper[f'class{i}']
                config = class_configs.get(cname, {})
                if not config:
                    continue
                preferred_periods = config.get("preferred_periods", [])
                is_double = config.get("double_period", False)

                for p in sorted(preferred_periods):
                    if is_double:
                        if p == 3 and 3 not in camper_periods[camper_id]:
                            camper_assignments[camper_id][p] = cname
                            camper_periods[camper_id].add(3)
                            class_rosters[cname][p].append(camper_id)
                        elif p in [1, 2] and p not in camper_periods[camper_id] and (p + 1) not in camper_periods[camper_id]:
                            camper_assignments[camper_id][p] = cname
                            camper_assignments[camper_id][p + 1] = cname
                            camper_periods[camper_id].add(p)
                            camper_periods[camper_id].add(p + 1)
                            class_rosters[cname][p].append(camper_id)
                    else:
                        if p not in camper_periods[camper_id]:
                            camper_assignments[camper_id][p] = cname
                            camper_periods[camper_id].add(p)
                            class_rosters[cname][p].append(camper_id)
                    if len(camper_assignments[camper_id]) >= 3:
                        break
                if len(camper_assignments[camper_id]) >= 3:
                    break

            if len(camper_assignments[camper_id]) == 0:
                unassignable_campers.append(camper_id)

        # Prepare camper assignments output
        camper_output = [["id", "P1", "P2", "P3"]]
        for camper in campers:
            cid = camper['id']
            row = [cid]
            for p in [1, 2, 3]:
                row.append(camper_assignments[cid].get(p, "Unassigned"))
            camper_output.append(row)

        # Write outputs directly
        camper_path = self._write_output("camper_assignments.csv", camper_output)
        inactive_path = self._write_output("skills_not_run.csv", 
            [["Class", "Period"]] + [[cname, p] for cname, p in inactive_classes])
        unassignable_path = self._write_output("camper_unassigned_log.csv", 
            [["id"]] + [[cid] for cid in unassignable_campers])

        print(f"Camper skill assignments saved to {camper_path}")
        print(f"Inactive Classes saved to {inactive_path}")
        print(f"Unassignable Campers saved to {unassignable_path}")

    def export_output_summary(self):
        """Create a summary log of all outputs (now just collects info since files are already written)"""
        log_summary = ["== Summary Log =="]
        log_summary.append(f"Timestamp: {self.timestamp}\n")

        # Check output files and gather stats
        output_files = {
            "day_off_results.csv": "✅ Day off assignments exported",
            "day_off_unassigned.csv": "⛔ Day off unassigned entries",
            "freetime_schedule.csv": "✅ Freetime schedule exported",
            "skills_schedule.csv": "✅ Skills schedule exported",
            "skills_unassigned.csv": "⛔ Skills unassigned entries",
            "coverage_schedule.csv": "✅ Coverage schedule exported",
            "camper_assignments.csv": "✅ Camper assignments exported",
            "skills_not_run.csv": "🚫 Skills not run",
            "camper_unassigned_log.csv": "😬 Campers not fully assigned"
        }

        for filename, message in output_files.items():
            path = os.path.join(self.output_dir, filename)
            if os.path.exists(path):
                if "unassigned" in filename or "not run" in filename:
                    with open(path, newline='') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        count = len(rows) - 1 if rows else 0
                    log_summary.append(f"{message}: {count}")
                else:
                    log_summary.append(message)
            else:
                log_summary.append(f"⚠️ Missing file: {filename}")

        # Write the summary log
        log_path = os.path.join(self.output_dir, "log.txt")
        with open(log_path, "w") as log_file:
            log_file.write("\n".join(log_summary))

        print(f"✅ Summary log created at {log_path}")

    def run_full_schedule(self):
        print("Starting scheduling process...")
        
        try:
            if not self.assign_off_times():
                print("Warning: Proceeding with limited day off data")
                
            self.assign_freetime_locations()
            self.load_staff_info()
            self.assign_skills_classes()
            self.assign_campers_to_skills()
            self.export_output_summary()
            
        except Exception as e:
            print(f"Scheduling failed: {str(e)}")
            # Create minimal output for debugging
            with open(os.path.join(self.output_dir, "ERROR_LOG.txt"), 'w') as f:
                f.write(f"Scheduling failed at {datetime.now()}\nError: {str(e)}")
            raise  # Re-raise if you want to see the full traceback
            
        print("Scheduling process completed!")