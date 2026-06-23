# Put Business OS on Railway

This build runs the website and API as one Railway service and stores business
data in Railway PostgreSQL.

## Railway project

1. Create an empty Railway project.
2. Add a PostgreSQL database.
3. Add a service from this Business OS repository.
4. In the app service, add these variables:
   - `DATABASE_URL=${{Postgres.DATABASE_URL}}`
   - `JWT_SECRET=` a long random private value
   - `ANTHROPIC_API_KEY=` your Claude API key
   - `ANTHROPIC_MODEL=claude-sonnet-4-5`
   - `TOKEN_HOURS=168`
5. In Networking, generate a public domain for the app service.

Do not put the Claude key or JWT secret in GitHub. Railway variables keep them
outside the code. The first visit to the public domain opens the owner setup.
