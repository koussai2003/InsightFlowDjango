# InsightFlow

InsightFlow is a planned data science workspace for cleaning, versioning and evaluating CSV datasets. The first implementation covers registration and role-based access with FastAPI, Vue and Supabase PostgreSQL. See [account setup and tests](docs/accounts.md) to run it.

## Planned workflow

1. Import and validate a CSV dataset while preserving the original.
2. Profile missing values, duplicates, column types, and basic statistics.
3. Preview a cleaning operation, confirm it, and save a new dataset version.
4. Explore distributions and relationships with charts and filters.
5. Train and compare baseline classification models using consistent metrics.
6. Add comments, review decisions, and export a report.

An AI assistant for explaining statistics and results is optional and will be confirmed during scope review.

## Team

- Rayen Selmi: data processing, AI and machine learning; Scrum Master.
- Aziz Labidi: backend, database, authentication and access control.
- Koussai Khelifi: frontend, user experience and charts.
- Shared responsibility: testing, integration, documentation and code review.

## Sprint 1: authentication and profiles

The initial Jira backlog contains five stories (16 Fibonacci story points): account registration, login, logout, profile editing, and role-based permissions. See the [Sprint 1 backlog](https://selmirayen369963.atlassian.net/jira/software/projects/IF/boards/3/backlog). Story points represent relative effort and uncertainty, not elapsed time. Sprint dates and duration should be reviewed with the team.

## Proposed technology

Vue 3 and Vite for the interface; FastAPI for the API; PostgreSQL for application metadata; Pandas, NumPy and scikit-learn for data processing and model evaluation. These are proposed choices and may change during design.

## Collaboration

Use Jira for stories and sprint tracking. Work in small branches, open pull requests for review, and link them to the relevant Jira story. Keep secrets and real datasets out of the repository.
