# Verification record

## Passing scoped checks

- Python/notebook syntax, JavaScript and inline HTML script syntax, selected credential patterns, private-file exclusions, source hashes and missing local script references.
- Shared speech text preparation: 3 language-mode smoke cases; no speech generated.
- Voice/weather runtime binding: 13 checks with a fake synthesizer, temporary SQLite, one booking socket, one forecast endpoint, final summary ownership, a shared speech-profile registry and preserved application source bytes.
- Real local HTTP backend integration: 28 checks using temporary accounts and SQLite. Covers fresh server startup, health/assets, protected endpoints, registration/login, owner-only listing, Mini-driver matching, SUV exclusion, idempotent submission, OTP visibility, scheduled listing, assigned-driver acceptance, missing-OTP rejection, valid-OTP start, completion and owner cancellation.
- Current customer-care engine: 270 deterministic fixture checks.
- Current customer-care API: 70 isolated provider/authentication fixture checks.
- Core booking/weather guard: 98 tests, executed before advanced integration bootstraps. One test was updated to the current requirement that the entire weather advisory is printed as well as spoken.

These counts cover different scopes. They must not be summed as independent user trials or an overall system accuracy.

## Inherited full-stack suite requiring review

The raw exported legacy guard suite was also run with the advanced modules enabled: 98 tests, 19 failures and 4 errors. That run predates the obsolete hidden-transcript assertion update. Several assertions assume older weather wording, status or consent stages; socket fixtures also time out and produce cleanup errors. The full set has not been rewritten or established as a passing final-system suite. Counts and notes are preserved in LEGACY_TEST_RESULTS.json.

The passing isolated core fixture suite and the passing new HTTP/binding checks do not erase those findings or establish complete voice-booking reliability.

## Reproduce scoped checks

```bash
python scripts/check_repository.py
python scripts/check_text_preparation.py
python scripts/check_runtime_binding.py
python scripts/check_backend_http.py
python scripts/run_component_checks.py
```

To investigate the inherited full-stack suite separately, run `python app/integrations/test_weather_guard.py app/server.py`. It writes temporary test logs; do not commit generated logs or databases.

## Required Kaggle/browser acceptance

Use a fresh GPU session and run MOVIO_Pipeline.ipynb from its first cell. Confirm all six stages finish, the shared HTTPS site opens, the customer and driver can sign in in separate profiles, a matching near-future booking appears, and OTP/cancellation work. Test voice booking, correction, weather keep/change choice, final confirmation and actual persisted booking ID in all three interaction modes. Listen to weather/summary audio and test the forecast button, popup/transcript, microphone permissions, companion geolocation allow/deny and consent-controlled tracking.

No new GPU speech-quality, full conversational latency, provider availability, real-user booking completion or security-audit result is claimed for this merged folder.

A working-folder ZIP does not capture live Python objects. Model loading and kernel-only speech configuration come from the latest available updated notebook; any later unshared in-memory changes require comparison during acceptance testing.
