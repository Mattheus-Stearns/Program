import csv
import random
from collections import defaultdict
import os

class ProgramSchedules:
    def __init__(self):
        self.index_data = {}  # key: ID, value: person info

    def assign_off_times(self):
        # TODO: consider a ratio of staff off

    # Load index.csv
        with open("index.csv", newline='') as index_file:
            reader = csv.DictReader(index_file)
            for row in reader:
                self.index_data[row['id']] = row  # Store full person data

        # Read off_times_form.csv from off_schedules directory
        off_schedule_path = os.path.join("off_schedules", "off_times_form.csv")
        assignments = []

        with open(off_schedule_path, newline='') as off_file:
            reader = csv.DictReader(off_file)
            for row in reader:
                person_id = row['id']
                if person_id not in self.index_data:
                    continue  # Skip if not found in index.csv

                # Choose random day and night from options
                day_off = random.choice([row['first option day'], row['second option day']])
                night_off = random.choice([row['first option night'], row['second option night']])

                # Collect the assignment
                assignments.append({
                    'id': person_id,
                    'name': row['name'],
                    'email': row['personal email'],
                    'day_off': day_off,
                    'night_off': night_off,
                    'notes': row['notes']
                })

        # Write to off_schedules/results.csv
        output_path = os.path.join("off_schedules", "results.csv")
        with open(output_path, mode='w', newline='') as result_file:
            fieldnames = ['id', 'name', 'email', 'day_off', 'night_off', 'notes']
            writer = csv.DictWriter(result_file, fieldnames=fieldnames)
            writer.writeheader()
            for entry in assignments:
                writer.writerow(entry)

        print(f"Assignment complete. Results saved to {output_path}")

def main():
    scheduler = ProgramSchedules()
    scheduler.assign_off_times()

if __name__ == "__main__":
    main()