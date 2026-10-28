# AI Ride Call

## Low-Latency Conversational AI for Weather-Aware Ride Management and Live Tracking

A browser-based ride-management system that brings together multilingual voice booking, manual booking, weather-aware travel assistance and customer–driver coordination.

Customers can plan a journey through the dashboard or speak naturally with the AI assistant in **English, Tamil or Tanglish**.

## Multilingual AI Voice Booking

- Book rides through a conversational AI Call page.
- Choose English, Tamil or Romanized Tanglish.
- Provide pickup, destination, passenger count, vehicle, date and time in one conversation.
- Retain journey details across turns and apply corrections to individual details.
- Review the journey summary and explicitly confirm before booking submission.
- Display the conversation transcript alongside spoken responses.
- Keep pronunciation preparation within the speech pipeline, separate from browser-visible text.

## Customer Dashboard

- Customer registration and sign-in.
- Manual ride booking with vehicle and passenger selection.
- Pickup and destination selection through address search, current location or map pins.
- Pickup date and time controls.
- Journey review with available road distance and estimated fare.
- Multiple bookings, saved booking details and cancellation controls.
- Driver and ride-status information after assignment.

## Journey Weather and Travel Advice

- Open-Meteo integration for journey forecasts.
- Separate pickup and destination forecast lookups using their coordinates and the selected pickup time.
- Weather condition, temperature and rain-probability information.
- Practical advice based on forecast conditions and the selected vehicle.
- Optional vehicle-change suggestions that respect the customer's decision.
- Weather advice in English, Tamil and Tanglish.
- Weather information displayed on the AI Call page and included in spoken assistance.
- **Listen to Forecast** playback from the customer dashboard.

## Your Travel Companion

- A compact customer-dashboard card for personalized travel suggestions.
- Permission-based current-location context and locality information.
- Weather-aware preparation advice, such as carrying an umbrella or drinking water.
- Contextual safety and readiness reminders.
- Relevant recommendations selected from journey details and available context.

## Driver Dashboard

- Driver registration and sign-in with vehicle details.
- Ride-request filtering by vehicle type.
- Accept and manage matching requests.
- View assigned journey details and update ride status.
- An informational upcoming-bookings panel for scheduled rides.
- Pickup OTP verification before starting the ride.
- Ride completion and customer-location request controls.

## Booking and Customer–Driver Coordination

- Account-linked booking records and backend-generated booking identifiers.
- Explicit confirmation before booking creation.
- Duplicate-submission protection through request identifiers.
- Guarded driver acceptance for competing requests.
- Four-digit pickup OTP handling.
- Booking cancellation and ride-status updates.

## Consent-Controlled Location Sharing

- Driver requests for customer location.
- Customer approval before sharing.
- Access restricted to the assigned driver.
- A time-limited sharing window with revocation controls.
- Map-based location and tracking views.

## Speech Experience

- Sarvam speech-to-text integration.
- Qwen2.5-3B-Instruct for structured dialogue extraction.
- Reference-conditioned DhVaani-0.5 speech synthesis.
- English and Tamil reference-audio support.
- Language-aware pronunciation preparation for transport terms and numerical entities.
- Semantic speech segmentation and queued playback.
- Cached reference conditioning and priority-based audio scheduling.
- Progressive forecast voice playback.

## Voice Recordings

The project includes a dedicated `Movio_Custom_Recordings/` collection for speech recordings and their accompanying metadata. The `metadata_master.csv` file uses these fields:

```csv
sample_id,audio_path,source,speaker_id,gender,language,category,raw_text,normalized_text,transcript
```

The metadata format covers recording identifiers, audio paths, source, speaker information, language, category and text/transcript fields.

## Technology Stack

| Area | Technology |
| --- | --- |
| Frontend | HTML, CSS and JavaScript |
| Application and voice services | Python, FastAPI and Uvicorn |
| Database | SQLite |
| Speech recognition | Sarvam STT |
| Language model | Qwen2.5-3B-Instruct |
| Speech synthesis | DhVaani-0.5 with a ZipVoice backend and Vocos |
| Weather | Open-Meteo |
| Geocoding and routing | OpenStreetMap/Nominatim and road-routing services |
| Execution environment | Kaggle GPU notebook |
| Public access | Shared HTTPS gateway through ngrok |

## Folder Structure

```text
MOVIO_AI_Ride/
├── README.md                    Project overview and features
├── MOVIO_Pipeline.ipynb          Main Kaggle startup notebook
├── pipeline.py                  Ordered startup controller
├── requirements.txt             Project dependencies
├── .env.example                 Configuration variable names
├── .gitignore                   Private and generated file exclusions
├── THIRD_PARTY.md               Third-party component information
├── app/
│   ├── server.py                Website and booking backend
│   ├── gateway.py               Shared website and voice gateway
│   ├── integrations/            Voice, booking, weather and care modules
│   └── web/                     Dashboard scripts, styles and assets
├── runtime/
│   ├── speech_adapters.py       Speech preparation and quality adapters
│   └── stages/                  Six ordered startup stages
│       ├── 01_models.py
│       ├── 02_speech.py
│       ├── 03_voice_configuration.py
│       ├── 04_weather_voice_binding.py
│       ├── 05_forecast_voice.py
│       └── 06_services.py
├── assets/
│   └── references/              Runtime English and Tamil TTS reference audio
├── Movio_Custom_Recordings/     Voice-recording collection
│   └── metadata_master.csv      Recording metadata and transcript fields
├── scripts/                     Repository and component checks
└── docs/                        Integration and technical records
```

The diagram shows the main application files and the recording collection. When uploading to GitHub, place the **contents** of `MOVIO_AI_Ride/` at the repository root.

## Unified Project Structure

The project includes a single startup notebook, `MOVIO_Pipeline.ipynb`, and an ordered pipeline covering model loading, speech preparation, voice configuration, weather integration, forecast playback and service startup.

The merged folder brings the website, voice services, weather modules, customer-care components and TTS reference resources together, with a dedicated location for the speech-recording collection.
