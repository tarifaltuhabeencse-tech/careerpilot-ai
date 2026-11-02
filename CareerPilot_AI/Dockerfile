FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY frontend frontend
ENV CAREERPILOT_DATABASE_URL=sqlite:////app/careerpilot.db
ENV CAREERPILOT_SECRET_KEY=change-me-before-production
EXPOSE 8000
CMD ["uvicorn","backend.app.main:app","--host","0.0.0.0","--port","8000"]
