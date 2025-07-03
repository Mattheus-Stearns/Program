# TODO: currently coordinators.json is just filled with random data, actually cross reference it with the actual index.csv file to ensure that the id's are correct and legit
# TODO: Make an actual index.csv file
from datetime import datetime, timedelta
from camp_scheduler.scheduler import ProgramSchedules
import argparse
import sys

def get_next_monday(today=None):
    today = today or datetime.today()
    days_ahead = (7 - today.weekday()) % 7  # 0 = Monday
    days_ahead = 7 if days_ahead == 0 else days_ahead  # force next week if today is Monday
    next_monday = today + timedelta(days=days_ahead)
    return next_monday.strftime("%d/%m/%Y")

def main():
    parser = argparse.ArgumentParser(
        description="Abnaki Program Scheduler CLI",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--week-start", "-w",
        help="Week start date in DD/MM/YYYY format. Default: next Monday."
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Define subcommands
    subparsers.add_parser("run-full-schedule", help="Run the full scheduling pipeline")
    subparsers.add_parser("assign-off-times", help="Assign off times")
    subparsers.add_parser("assign-freetime-locations", help="Assign freetime locations")
    subparsers.add_parser("generate-coverage-schedule", help="Generate coverage schedule")
    subparsers.add_parser("assign-skills-classes", help="Assign skills classes for staff")
    subparsers.add_parser("assign-campers-to-skills", help="Assign campers to skills classes")

    # For legacy compatibility, allow --run-full-schedule, etc.
    parser.add_argument("--run-full-schedule", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--assign-off-times", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--assign-freetime-locations", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--generate-coverage-schedule", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--assign-skills-classes", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--assign-campers-to-skills", action="store_true", help=argparse.SUPPRESS)

    # Custom help
    parser.add_argument("help", nargs="?", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # Show help if requested
    if args.help == "help" or (len(sys.argv) == 2 and sys.argv[1] == "help"):
        print("""
Abnaki Program Scheduler CLI

Usage:
  python3 app.py [--week-start DD/MM/YYYY] <command>

Commands:
  run-full-schedule         Run the full scheduling pipeline (all steps)
  assign-off-times          Assign off times to staff
  assign-freetime-locations Assign freetime locations for staff
  generate-coverage-schedule Generate the coverage schedule
  assign-skills-classes     Assign skills classes for staff
  assign-campers-to-skills  Assign campers to skills classes

Examples:
  python3 app.py run-full-schedule
  python3 app.py --week-start 07/07/2025 assign-campers-to-skills

You can also use legacy flags:
  python3 app.py --run-full-schedule
""")
        sys.exit(0)

    # Parse week start date
    if args.week_start:
        try:
            week_start_date = datetime.strptime(args.week_start, "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            print("Error: Date must be in format DD/MM/YYYY")
            sys.exit(1)
    else:
        week_start_date = get_next_monday()

    scheduler = ProgramSchedules(week_start_date)

    # Command dispatch
    if args.command == "run-full-schedule" or args.run_full_schedule:
        scheduler.run_full_schedule()
    elif args.command == "assign-off-times" or args.assign_off_times:
        scheduler.assign_off_times()
    elif args.command == "assign-freetime-locations" or args.assign_freetime_locations:
        scheduler.assign_freetime_locations()
    elif args.command == "generate-coverage-schedule" or args.generate_coverage_schedule:
        scheduler.generate_coverage_schedule()
    elif args.command == "assign-skills-classes" or args.assign_skills_classes:
        scheduler.assign_skills_classes()
    elif args.command == "assign-campers-to-skills" or args.assign_campers_to_skills:
        scheduler.assign_campers_to_skills()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
