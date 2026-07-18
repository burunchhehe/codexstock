from stock_suite import StockSuite, available_projects


def main() -> None:
    suite = StockSuite()
    print("Projects:")
    for project in available_projects():
        print(f"- {project.name}: {project.role}")
    print()
    print(f"Lean solution: {suite.engine.solution_file}")


if __name__ == "__main__":
    main()
