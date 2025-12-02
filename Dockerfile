# --- STAGE 1: Build Frontend (Node) ---
FROM node:18-alpine as frontend_builder
WORKDIR /frontend_build
COPY ./frontend/package.json ./
RUN npm install
COPY ./frontend ./
RUN npm run build

# --- STAGE 2: Setup Backend (Python) ---
FROM python:3.9-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential
COPY ./backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./backend .

# --- STAGE 3: Merge ---
COPY --from=frontend_builder /frontend_build/build ./static
RUN chmod +x start.sh
ENV PORT=8000
CMD ["./start.sh"]
