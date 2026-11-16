# On Air — attribute contract

`contract_version: 1`

This is the only interface between the On Air integration and any card. A card reads these attributes and computes nothing: every value it shows is here.

## Entities

One sensor per selected channel: `sensor.on_air_<channel>` (for example `sensor.on_air_rai_1`), all under the service device "On Air".

## State

The title of the programme on air, truncated to 255 characters (Home Assistant state limit). The full title is in `now.title`.

- `unknown`: the guide has nothing for the current time on this channel (a gap in the guide, or a channel missing from every source).
- `unavailable`: no guide data could be loaded at all (every source failed and nothing was kept from earlier downloads).

## Attributes

| Attribute | Type | Meaning |
|---|---|---|
| `contract_version` | int | `1` |
| `channel_name` | string | Readable channel name, e.g. `Rai 1`, `Sky Uno +1` |
| `now` | programme or `null` | Programme on air (`start <= now < end`); `null` in a gap |
| `next` | programme or `null` | First programme after `now` (or after the current time in a gap); `null` when it is beyond the downloaded guide |
| `tonight` | list of programmes | Programmes overlapping `tonight_window`, sorted by start; may include one that started before the window; `[]` when there is no data |
| `tonight_window` | object | `start`, `end`: ISO 8601 datetimes. Default 20:00–00:00 local; before 06:00 it is still the previous evening |
| `updated_at` | ISO 8601 or `null` | Last successful download of any source |
| `sources` | object | Per source id (`open_epg`, `iptv_epg`): `status` (`ok` or `error`) and `updated_at` (ISO 8601 or `null`) |

A **programme** is an object:

| Field | Type | Meaning |
|---|---|---|
| `title` | string | Title as given by the source (never truncated here); filler rows (`No Data`, `No Game Today`, `Next Game: …`, date-only titles) are dropped; the other source can fill the gap |
| `start`, `end` | ISO 8601 | Local time zone of Home Assistant, with offset |
| `category` | string or `null` | Category from the guide (e.g. `Film`, `Sport`), with known spelling variants unified (`Sports` → `Sport`, `Documentari` → `Documentario`); `null` when no source has one |
| `source` | string | Source the title comes from |

`null` means "not known"; it is never replaced by a guess.

## Recorder

`next`, `tonight` and `tonight_window` are excluded from the recorder database (`_unrecorded_attributes`). History keeps the state and `now`.

## Versioning

`contract_version` changes only for changes that break existing cards: renaming or removing an attribute, or changing its meaning. New attributes or new values are additive and keep the version.
