# Home Assistant Calendar Skill

Interact with your Google Calendar through Home Assistant.

## Setup

1.  **Home Assistant Integration:** Ensure your Google Calendar is added as an integration in Home Assistant.
2.  **Entity ID:** Find the correct `entity_id` for your calendar (e.g., `calendar.viniciusmathias@gmail.com`).
3.  **Environment Variables:** Ensure `HOMEASSISTANT_URL` and `HOMEASSISTANT_TOKEN` are set in the agent's environment.

## Usage

Use the `exec` tool to run the helper script. The script requires an action, the calendar entity ID, and optional details.

### Actions

-   **List Events (`list`)**: Get a list of events from a calendar.
    ```bash
    data/skills/homeassistant/calendar_skill.sh list calendar.viniciusmathias@gmail.com
    ```

-   **Get Event Details (`get`)**: Get details for a specific event (requires event ID or date).
    ```bash
    # Example for an event on a specific date (YYYY-MM-DD)
    data/skills/homeassistant/calendar_skill.sh get calendar.viniciusmathias@gmail.com 2026-02-03
    ```

-   **Add Event (`add`)**: Add a new event to the calendar.
    *Note: This action requires a JSON payload with event details (summary, start time, end time, etc.).*
    ```bash
    # Example payload (replace with actual details)
    # PAYLOAD='{"summary": "Reuniao de Pais", "dtstart": "2026-02-05T10:00:00", "dtend": "2026-02-05T11:00:00"}'
    # data/skills/homeassistant/calendar_skill.sh add calendar.viniciusmathias@gmail.com "$PAYLOAD"
    ```
