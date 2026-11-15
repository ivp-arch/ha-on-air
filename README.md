# On Air

Home Assistant integration that shows what is on Italian TV **now** and **tonight**, for digital terrestrial (DTT) and Sky/NOW linear channels, from free XMLTV guides.

One sensor per selected channel: the state is the programme on air; the attributes carry the next programme and the evening schedule. A matching Lovelace card lives in [ha-on-air-card](https://github.com/ivp-arch/ha-on-air-card).

> On demand catalogues (Netflix, Prime Video, Disney+, NOW on demand) have no schedule and are out of scope.

## How it works

- Downloads two free guides every 12 hours: [open-epg.com](https://www.open-epg.com/) (more specific titles) and [iptv-epg.org](https://iptv-epg.org/) (categories, longer horizon). They are merged per channel: open-epg gives the titles, iptv-epg fills the gaps and adds categories.
- If a source fails, its last good data is kept and the other source still updates.
- Sensors do not poll: each one updates at the next programme change and at 06:00, when "tonight" moves to the new day.
- Parsing runs outside the event loop and keeps only the selected channels.

These are third-party guides, free and unofficial: they can change address, format or coverage at any time. Both URLs can be changed in the options.

## Installation

Manual: copy `custom_components/on_air` into the `custom_components` folder of your Home Assistant configuration and restart Home Assistant.

## Configuration

Settings → Devices & services → Add integration → **On Air**.

1. **Guide sources**: both URLs are pre-filled; leave one empty to skip that source.
2. **Channels**: the main channels are preselected (Rai 1–3, Rete 4, Canale 5, Italia 1, Sky Uno, Sky Atlantic, Sky Serie, Sky Cinema Uno, Sky Sport Uno). Add single channels from the full list, or whole groups (Rai, Mediaset, Sky Cinema, Sky Sport, Sky entertainment); groups skip the +1 and +24 versions.

Options: sources, channels, groups and the "tonight" window (default 20:00–00:00).

## Entities

`sensor.on_air_<channel>` (e.g. `sensor.on_air_rai_1`), all under the "On Air" service device.

- State: title on air; `unknown` when the guide has nothing for the current time.
- Attributes: `now`, `next`, `tonight`, `tonight_window`, `updated_at`, `sources`, `channel_name`, `contract_version`. Full description in [docs/attributes-contract.md](docs/attributes-contract.md).

`next`, `tonight` and `tonight_window` are not stored in the recorder database.

## Development

```bash
pip install -r requirements_test.txt   # Python 3.14
pytest
```

Tests use XMLTV fixtures and mocked HTTP: no network needed. See [CLAUDE.md](CLAUDE.md) for the project rules.

## License

MIT
