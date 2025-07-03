import csv
import random
from datetime import datetime, timedelta

def generate_off_times_csv(filename="off_times_form.csv", start_date_str="07/07/2025", num_staff=60):
    # Parse the start date (Monday)
    start_date = datetime.strptime(start_date_str, "%d/%m/%Y")
    week_dates = [(start_date + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]  # Mon-Sun
    
    notes_options = ["", "Prefers early week", "Avoid Wednesdays"]
    # "Early week" means preferring Mon-Wed days

    def pick_day_option(prefer_early=False):
        if prefer_early:
            choices = week_dates[:3]  # Mon, Tue, Wed
        else:
            choices = week_dates
        first = random.choice(choices)
        second_choices = [d for d in choices if d != first]
        second = random.choice(second_choices) if second_choices else first
        return first, second

    def pick_night_option(prefer_early=False):
        # For night off, we allow full week as well but with some preference possibility
        return pick_day_option(prefer_early)

    with open(filename, mode="w", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "personal email", "name",
            "first option day", "second option day",
            "first option night", "second option night",
            "notes"
        ])

        for i in range(num_staff):
            email = f"staff{i}@camp.org"
            name = f"Staff Member {i}"
            
            note = random.choices(notes_options, weights=[0.6, 0.25, 0.15])[0]
            prefer_early = (note == "Prefers early week")

            first_day, second_day = pick_day_option(prefer_early)
            first_night, second_night = pick_night_option(prefer_early)

            writer.writerow([
                email, name,
                first_day, second_day,
                first_night, second_night,
                note
            ])

    print(f"Generated {filename} with {num_staff} staff entries.")

def generate_camper_choices_csv(filename="camper_choices.csv", num_campers=150):
    classes = {
        "Waterfront": {"camper_assignable": False},
        "Basketball": {"camper_assignable": True},
        "Tennis": {"camper_assignable": True},
        "Sailing": {"camper_assignable": True},
        "High Ropes": {"camper_assignable": True},
        "Program": {"camper_assignable": False},
        "Attendance": {"camper_assignable": False},
        "Fishing": {"camper_assignable": True},
        "Survival": {"camper_assignable": True},
        "Archery": {"camper_assignable": True},
        "Volleyball": {"camper_assignable": True},
        "Floor Hockey": {"camper_assignable": True},
        "Arts & Crafts": {"camper_assignable": True},
        "Office/Admin Help": {"camper_assignable": False},
        "DnD": {"camper_assignable": True},
        "Dodgeball": {"camper_assignable": True},
        "Snorkeling": {"camper_assignable": True},
        "Diamond Sports": {"camper_assignable": True},
        "Soccer": {"camper_assignable": True},
        "Leisure Sports": {"camper_assignable": True},
        "Skateboarding": {"camper_assignable": True},
        "BFS": {"camper_assignable": True},
        "Skull Session": {"camper_assignable": False},
        "Flag Football": {"camper_assignable": True}
    }

    assignable_classes = [name for name, cfg in classes.items() if cfg["camper_assignable"]]

    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["id", "name", "cabin", "class1", "class2", "class3", "class4", "class5", "submission_time"])

        for i in range(1001, 1001 + num_campers):
            name = f"Camper {i}"
            cabin = f"Cabin {random.randint(1, 10)}"
            class_choices = random.sample(assignable_classes, 5)
            submission_time = datetime(2025, 6, 30, random.randint(8, 18), random.randint(0, 59)).strftime("%Y-%m-%d %H:%M")
            writer.writerow([i, name, cabin] + class_choices + [submission_time])

    print(f"Generated {filename} with {num_campers} campers.")

if __name__ == "__main__":
    generate_off_times_csv()
    generate_camper_choices_csv()