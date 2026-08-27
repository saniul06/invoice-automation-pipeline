The application is Dockerized, You just need docker to run the project. Also don't forget to run the accounting server as well. I put a GEMINI_API_KEY in the .env file for your convenience. But when it will reach the limit, you need to add another GEMINI_API_KEY there.

To run:

```bash
docker compose up --build
```

Place invoice files in:

```text
invoices/
```

Processed results ( Whether it is Completed / In Review / Failed ) are written to:

```text
output/
```
