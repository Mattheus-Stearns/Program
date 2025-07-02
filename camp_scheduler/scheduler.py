# TODO: Handle double periods starting P3 affecting freetime coverage
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

    def _write_output(self, filename, content):
        """Helper to write output files directly to output directory"""
        path = os.path.join(self.output_dir, filename)
        
        if isinstance(content, pd.DataFrame):
            content.to_csv(path, index=False)
        elif isinstance(content, list) and content and isinstance(content[0], dict):
            # Handle list of dictionaries
            df = pd.DataFrame(content)
            df.to_csv(path, index=False)
        elif isinstance(content, list):
            # Handle list of lists (rows)
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(content)
        else:
            with open(path, 'w') as f:
                f.write(str(content))
        return path

    def _is_consecutive(self, date1_str, date2_str):
        """Return True if two dates are consecutive calendar days (in either order)"""
        try:
            date1 = datetime.strptime(date1_str, "%d/%m/%Y")
            date2 = datetime.strptime(date2_str, "%d/%m/%Y")
            return abs((date1 - date2).days) == 1
        except:
            return False

    def assign_off_times(self):
        try:
            # Load configuration files
            with open(self._get_data_path("dates.json")) as f:
                dates_config = json.load(f)
            with open(self._get_data_path("off_times_form.csv")) as f:
                off_requests = list(csv.DictReader(f))
            with open(self.index_path) as f:
                self.index_data = {row['id']: row for row in csv.DictReader(f)}

            # Process blackout periods with 1-day buffer
            blackout_days = set()
            for period in dates_config["blackout_periods"].values():
                start = datetime.strptime(period["start"], "%Y-%m-%d")
                end = datetime.strptime(period["end"], "%Y-%m-%d")
                blackout_days.update([
                    start - timedelta(days=1),
                    start,
                    end,
                    end + timedelta(days=1)
                ])

            # Helper functions
            def is_valid_date(date_str):
                try:
                    date = datetime.strptime(date_str, "%d/%m/%Y")
                    return date not in blackout_days
                except ValueError:
                    return False

            def has_coverage_conflict(staff_id, date_str, time_type):
                coverage_id = self.index_data.get(staff_id, {}).get("coverage", "").strip()
                if not coverage_id:
                    return False
                co_staff_assignments = staff_assignments.get(coverage_id, {})
                return co_staff_assignments.get(time_type) == date_str

            def has_cabin_conflict(staff_id, date_str):
                """New: Prevent any same-date off within cabin (day or night)"""
                department = self.index_data.get(staff_id, {}).get("department", "")
                if not department or department in ["Program", "Admin", "Maintenance"]:
                    return False  # Skip non-cabin staff
                
                for mate_id, mate_data in self.index_data.items():
                    if (mate_id != staff_id and 
                        mate_data.get("department") == department and
                        (staff_assignments.get(mate_id, {}).get("day") == date_str or
                        staff_assignments.get(mate_id, {}).get("night") == date_str)):
                        return True
                return False

            # Initialize tracking
            assignments = []
            unassigned_log = []
            used_days = defaultdict(set)
            used_nights = defaultdict(set)
            staff_assignments = defaultdict(dict)
            max_per_slot = max(1, int(len(self.index_data) * 0.25))

            # Process each staff member
            for request in off_requests:
                person_id = request['id']
                if person_id not in self.index_data:
                    continue

                assignment = {
                    'id': person_id,
                    'name': request['name'],
                    'email': request['personal email'],
                    'day_off': "Unassigned",
                    'night_off': "Unassigned",
                    'notes': request.get('notes', ''),
                    'assignment_type': 'Unassigned'
                }

                # Try preferred day off
                day_options = [d for d in [request['first option day'], request['second option day']] if d]
                for option in day_options:
                    if (is_valid_date(option) and
                        len(used_days[option]) < max_per_slot and
                        not has_coverage_conflict(person_id, option, 'day') and
                        not has_cabin_conflict(person_id, option)):  # New check
                        assignment['day_off'] = option
                        assignment['assignment_type'] = 'Preferred'
                        used_days[option].add(person_id)
                        staff_assignments[person_id]['day'] = option
                        break

                # Try preferred night off
                night_options = [d for d in [request['first option night'], request['second option night']] if d]
                for option in night_options:
                    if (is_valid_date(option) and
                        len(used_nights[option]) < max_per_slot and
                        not has_coverage_conflict(person_id, option, 'night') and
                        not has_cabin_conflict(person_id, option) and  # New check
                        not (assignment['day_off'] != "Unassigned" and 
                            self._is_consecutive(assignment['day_off'], option))):
                        assignment['night_off'] = option
                        assignment['assignment_type'] = 'Preferred'
                        used_nights[option].add(person_id)
                        staff_assignments[person_id]['night'] = option
                        break

                # Automatic assignment fallback
                all_dates = [
                    (self.week_start_date + timedelta(days=x)).strftime("%d/%m/%Y") 
                    for x in range(7)
                ]
                valid_dates = [d for d in all_dates if is_valid_date(d)]

                if assignment['day_off'] == "Unassigned":
                    available_days = [
                        d for d in valid_dates 
                        if (len(used_days[d]) < max_per_slot and
                            not has_coverage_conflict(person_id, d, 'day') and
                            not has_cabin_conflict(person_id, d))
                    ]
                    if available_days:
                        day_off = random.choice(available_days)
                        assignment['day_off'] = day_off
                        assignment['assignment_type'] = 'Automatic'
                        used_days[day_off].add(person_id)
                        staff_assignments[person_id]['day'] = day_off

                if assignment['night_off'] == "Unassigned":
                    available_nights = [
                        d for d in valid_dates 
                        if (len(used_nights[d]) < max_per_slot and
                            not has_coverage_conflict(person_id, d, 'night') and
                            not has_cabin_conflict(person_id, d) and
                            not (assignment['day_off'] != "Unassigned" and 
                                self._is_consecutive(assignment['day_off'], d)))
                    ]
                    if available_nights:
                        night_off = random.choice(available_nights)
                        assignment['night_off'] = night_off
                        assignment['assignment_type'] = 'Automatic'
                        used_nights[night_off].add(person_id)
                        staff_assignments[person_id]['night'] = night_off

                assignments.append(assignment)

                # Log unassigned
                if assignment['day_off'] == "Unassigned" or assignment['night_off'] == "Unassigned":
                    reason = []
                    if assignment['day_off'] == "Unassigned":
                        reason.append("day: no valid slot")
                    if assignment['night_off'] == "Unassigned":
                        reason.append("night: no valid slot")
                    unassigned_log.append({**assignment, 'reason': "; ".join(reason)})

            # Write outputs
            self._write_output("time_off_results.csv", assignments)
            self._write_output("time_off_unassigned.csv", unassigned_log)
            
            return assignments

        except Exception as e:
            print(f"Error in assign_off_times: {str(e)}")
            empty = [{'id': '', 'name': '', 'email': '', 'day_off': '', 'night_off': '', 'notes': '', 'assignment_type': ''}]
            self._write_output("time_off_results.csv", empty)
            self._write_output("time_off_unassigned.csv", empty)
            return []

    def assign_freetime_locations(self):
        try:
            # Load index.csv
            with open(self.index_path, newline='') as index_file:
                reader = csv.DictReader(index_file)
                for row in reader:
                    self.index_data[row['id']] = row

            # Load off_schedules/results.csv from output
            off_results_path = os.path.join(self.output_dir, "time_off_results.csv")
        
            if not os.path.exists(off_results_path):
                raise FileNotFoundError("time_off_results.csv not found")
                
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
        """
        Assigns coverage for staff who are OFF during their preferred periods, for each day.
        days_off_schedule: {staff_id: [periods_off]}  # e.g., { "101": [1, 3], ... }
        staff_skills_schedule: {staff_id: {day: {period: assignment_dict}}}
        staff_data: dict of staff info
        """
        coverage_schedule = defaultdict(lambda: defaultdict(lambda: None))
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        periods = [1, 2, 3]

        # Build a lookup for which staff are OFF each (day, period)
        off_by_day_period = defaultdict(list)
        for staff_id, off_periods in days_off_schedule.items():
            for day in weekdays:
                for period in off_periods:
                    off_by_day_period[(day, period)].append(int(staff_id))

        # For each (day, period) where someone is OFF, find a cover
        for (day, period), off_staff_ids in off_by_day_period.items():
            for off_id in off_staff_ids:
                available_staff = []
                for candidate_id in staff_data:
                    if int(candidate_id) == int(off_id):
                        continue
                    # Skip if candidate is also OFF this period (from days_off_schedule)
                    candidate_off_periods = days_off_schedule.get(str(candidate_id), []) or days_off_schedule.get(int(candidate_id), [])
                    if period in candidate_off_periods:
                        continue
                    # Skip if candidate is already assigned to a class (not OFF or Help)
                    assignment = staff_skills_schedule.get(candidate_id, {}).get(day, {}).get(period)
                    if assignment and assignment['class'] not in ['OFF', 'Help', 'Unassigned']:
                        continue
                    available_staff.append(candidate_id)

                if available_staff:
                    assigned_cover = available_staff[0]
                    coverage_schedule[assigned_cover][f"{day} P{period}"] = f"Cover for {off_id}"
                else:
                    print(f"[Warning] No available staff to cover {off_id} during {day} P{period}")

        return coverage_schedule

    def assign_skills_classes(self):
        # Load required data
        with open(self._get_data_path("classes.json")) as f:
            class_configs = json.load(f)
        with open(self._get_data_path("fixed_skills_off.json")) as f:
            fixed_off_periods = json.load(f)

        staff_df = pd.read_csv(self.index_path)
        staff_data = staff_df.set_index("id").to_dict("index")

        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        periods = [1, 2, 3]

        # --- 1. Assign fixed weekly pattern for each staff member ---

        period_class_needs = {p: [] for p in periods}
        for class_name, config in class_configs.items():
            for period in config["preferred_periods"]:
                if config.get("double_period") and period == 3:
                    continue
                for n in range(config["staff_required"]):
                    period_class_needs[period].append((class_name, config))

        staff_weekly_pattern = {}
        assigned_classes = set()
        for staff_id, info in staff_data.items():
            pattern = [None, None, None]
            for class_name, config in class_configs.items():
                if staff_id in config.get("coordinators", []):
                    for i, period in enumerate(periods):
                        if period in config["preferred_periods"]:
                            if config.get("double_period") and period == 3:
                                continue
                            pattern[i] = {"class": class_name, "role": "lead"}
                            assigned_classes.add((period, class_name, staff_id))
                            break
            staff_weekly_pattern[staff_id] = pattern

        # --- UPDATED: Use new fixed_skills_off.json structure ---
        for staff_id, off_periods in fixed_off_periods.items():
            pattern = staff_weekly_pattern.get(int(staff_id), [None, None, None])
            for i, period in enumerate(periods):
                if period in off_periods and pattern[i] is None:
                    pattern[i] = {"class": "OFF", "role": "none"}
                    break
            staff_weekly_pattern[int(staff_id)] = pattern

        for staff_id, info in staff_data.items():
            pattern = staff_weekly_pattern.get(staff_id, [None, None, None])

            # Determine which period to assign OFF first (if not fixed already)
            off_assigned = any(x and x["class"] == "OFF" for x in pattern)
            if not off_assigned:
                # Find period with least demand to assign OFF
                period_off_candidates = sorted(periods, key=lambda p: len(period_class_needs[p]))
                for p in period_off_candidates:
                    if pattern[p - 1] is None:
                        pattern[p - 1] = {"class": "OFF", "role": "none"}
                        break

            # Assign two classes
            assigned_count = sum(1 for x in pattern if x and x["class"] not in ("OFF", "Help"))
            for i, period in enumerate(periods):
                if pattern[i] is not None or assigned_count >= 2:
                    continue
                for idx, (class_name, config) in enumerate(period_class_needs[period]):
                    if staff_id in config.get("coordinators", []):
                        continue
                    if any(x and x.get("class") == class_name for x in pattern):
                        continue
                    if class_name == "Waterfront" and info["lifeguard certification"] != "Yes":
                        continue
                    if class_name == "Archery" and info["archery certification"] != "Yes":
                        continue
                    if class_name == "High Ropes" and info["high ropes certification"] != "Yes":
                        continue
                    if class_name == "Fishing" and info["fishing proficiency"] != "Yes":
                        continue

                    # Handle double-periods
                    if config.get("double_period", False):
                        if period == 3 or i >= 2:
                            continue  # No room for double period at P3
                        if pattern[i + 1] is not None:
                            continue  # Next period already filled
                        # Assign both periods
                        role = "assistant"
                        if class_name == "Fishing" and info["fishing proficiency"] == "Yes":
                            role = "lead"
                        pattern[i] = {"class": class_name, "role": role}
                        pattern[i + 1] = {"class": class_name, "role": role}
                        assigned_classes.add((period, class_name, staff_id))
                        assigned_classes.add((period + 1, class_name, staff_id))
                        del period_class_needs[period][idx]
                        assigned_count += 2
                        break
                    else:
                        role = "assistant"
                        if class_name == "Fishing" and info["fishing proficiency"] == "Yes":
                            role = "lead"
                        pattern[i] = {"class": class_name, "role": role}
                        assigned_classes.add((period, class_name, staff_id))
                        del period_class_needs[period][idx]
                        assigned_count += 1
                        break

            # Fallback fill: if any unassigned left, mark as Help (but ensure exactly 1 OFF remains)
            off_count = sum(1 for x in pattern if x and x["class"] == "OFF")
            for i in range(3):
                if pattern[i] is None:
                    if off_count < 1:
                        pattern[i] = {"class": "OFF", "role": "none"}
                        off_count += 1
                    else:
                        pattern[i] = {"class": "Help", "role": "none"}

            staff_weekly_pattern[staff_id] = pattern

        # --- 2. Build the full weekly schedule for each staff member ---
        staff_daily_schedule = defaultdict(lambda: defaultdict(dict))
        class_assignments = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        unassigned_log = []

        for staff_id, pattern in staff_weekly_pattern.items():
            for day in weekdays:
                for idx, period in enumerate(periods):
                    entry = pattern[idx]
                    staff_daily_schedule[staff_id][day][period] = entry
                    if entry["class"] not in ["OFF", "Help"]:
                        class_assignments[day][period][entry["class"]].append((staff_id, entry["role"]))

        # --- 3. Prepare skills schedule output as id,name,P1,P2,P3 ---
        skills_output = []
        header = ["id", "name", "P1", "P2", "P3"]
        skills_output.append(header)
        for staff_id in staff_data:
            row = [staff_id, staff_data[staff_id].get("name", "")]
            for idx in range(3):
                entry = staff_weekly_pattern[staff_id][idx]
                if entry["class"] == "OFF":
                    row.append("OFF")
                elif entry["class"] == "Help":
                    row.append("Help")
                elif entry["role"] == "lead":
                    row.append(f"Lead {entry['class']}")
                elif entry["role"] == "assistant":
                    row.append(f"Assistant {entry['class']}")
                else:
                    row.append("Unassigned")
            skills_output.append(row)

        skills_path = self._write_output("skills_schedule.csv", skills_output)

        # --- 4. Write unassigned log (should be empty) ---
        for staff_id in staff_data:
            for day in weekdays:
                for period in periods:
                    if not staff_daily_schedule[staff_id][day][period]:
                        unassigned_log.append({"id": staff_id, "day": day, "period": period})
        unassigned_path = self._write_output("skills_unassigned.csv", 
            [["id", "day", "period"]] + [[x["id"], x["day"], x["period"]] for x in unassigned_log])

        self.skills_schedule = class_assignments
        self.skills_by_staff = staff_daily_schedule

        # --- 5. Generate coverage schedule ---
        coverage_schedule = self.generate_coverage_schedule(staff_daily_schedule, fixed_off_periods, staff_data)

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
            "time_off_results.csv": "✅ Day off assignments exported",
            "time_off_unassigned.csv": "⛔ Day off unassigned entries",
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