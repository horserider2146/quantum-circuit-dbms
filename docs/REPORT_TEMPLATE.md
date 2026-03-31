# Report Template (10-12 pages)

Use this structure directly for the course submission PDF.

## 1. Problem Statement (1.5-2 pages)
- Domain selected
- Why this data is interesting
- What business/analytical decisions are enabled
- Data story: trends over time, category comparisons, and performance analysis

## 2. Database Design and Justification (2-2.5 pages)
- Database choice and workload fit
- Normalization strategy and table relationships
- Primary key and relational keys
- Indexing strategy and expected query impact
- Include ER diagram from `docs/ER_DIAGRAM.md`

## 3. API Documentation and CRUD Mapping (2 pages)
- Endpoint summary table (method, route, purpose)
- CRUD mapping to user operations
- Authentication design (`X-API-Key`)
- Pydantic request and response validation
- Swagger screenshot and short explanation

## 4. Dashboard Description and Insight (2 pages)
- Visualization 1: KPI cards and what they indicate
- Visualization 2: algorithm/backends distribution
- Visualization 3: fidelity distribution / top performers table
- Interactive controls: search + filters
- Refresh strategy: manual and auto-polling modes with rationale

## 5. SQL Commands Used (1-1.5 pages)
- Include SQL examples from `sql/sample_queries.sql`
- Aggregations, joins, trend queries
- One insert, one update, one delete example

## 6. Challenges and Learnings (1-1.5 pages)
- Implementation issues encountered
- Data cleaning/typing constraints
- API and frontend integration lessons
- What would be improved in a production version

## Appendix Suggestions
- Screenshots from dashboard pages
- Swagger endpoint screenshots
- Representative API request/response examples
- Team contribution split (if required by instructor)
