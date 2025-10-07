# Notetaking Assistant

## Overview
Notetaking Assistant is a project designed to help users schedule meetings, transcribe recordings, and manage calendar events efficiently. It includes a backend built with FastAPI and a frontend for user interaction.

---

## How to Execute

### Backend
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the backend server:
   ```bash
   uvicorn main:app --reload
   ```
   The backend will be available at `http://127.0.0.1:8000`.

### Frontend
1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Open the `index.html` file in your browser to start the frontend.

---

## Deployment
This project is configured for deployment on Vercel. Ensure the `vercel.json` files are correctly set up for both the frontend and backend.

---

## Environment Variables
Ensure the following environment variables are set in the `.env` file in the `backend` directory:
- `NYLAS_API_KEY`
- `NYLAS_GRANT_ID`
- `MONGO_URI`

---

## License
This project is licensed under the MIT License.