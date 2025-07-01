# TODO: currently coordinators.json is just filled with random data, actually cross reference it with the actual index.csv file to ensure that the id's are correct and legit
# TODO: Make an actual index.csv file
# TODO: Make use of dates.json

from datetime import datetime, timedelta
from camp_scheduler.scheduler import ProgramSchedules
import sys

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
    scheduler.run_full_schedule()

if __name__ == "__main__":
    main()