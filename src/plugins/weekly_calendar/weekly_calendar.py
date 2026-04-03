"""Weekly Calendar plugin — 7-column weekly board with event time + title rows."""

from datetime import datetime, timedelta, date

from PIL import Image, ImageColor, ImageDraw

from plugins.calendar.calendar import Calendar
from plugins.calendar.constants import FONT_SIZES
from utils.app_utils import get_font
from utils.text_utils import get_text_dimensions


class WeeklyCalendar(Calendar):
    """Calendar variant that renders a compact 7-column weekly event board."""

    def _luma(self, color):
        r, g, b = ImageColor.getrgb(color)
        return (r * 299 + g * 587 + b * 114) / 1000

    def _readable_text_color(self, preferred_color, bg_color):
        """Return a readable text color for the configured background."""
        try:
            pref_luma = self._luma(preferred_color)
            bg_luma = self._luma(bg_color)
            # If configured text color has poor contrast, switch to black/white.
            if abs(pref_luma - bg_luma) < 110:
                return self.get_contrast_color(bg_color)
            return preferred_color
        except Exception:
            return "#000000"

    def _wrap_text(self, draw, text, font, max_width):
        """Word-wrap text without truncation."""
        words = text.split()
        if not words:
            return [""]

        lines = []
        current = words[0]

        for word in words[1:]:
            candidate = f"{current} {word}"
            if get_text_dimensions(draw, candidate, font)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word

        lines.append(current)

        # Break extremely long unspaced tokens if needed.
        expanded = []
        for line in lines:
            if get_text_dimensions(draw, line, font)[0] <= max_width:
                expanded.append(line)
                continue

            chunk = ""
            for ch in line:
                candidate = f"{chunk}{ch}"
                if chunk and get_text_dimensions(draw, candidate, font)[0] > max_width:
                    expanded.append(chunk)
                    chunk = ch
                else:
                    chunk = candidate
            if chunk:
                expanded.append(chunk)

        return expanded or [""]

    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["settings_template"] = "weekly_calendar/settings.html"
        return template_params

    def generate_image(self, settings, device_config):
        import pytz

        settings = dict(settings or {})
        calendar_urls = settings.get("calendarURLs[]")
        calendar_colors = settings.get("calendarColors[]")

        if calendar_urls:
            calendar_urls = [url for url in calendar_urls if url.strip()]
            if calendar_colors and len(calendar_colors) > len(calendar_urls):
                calendar_colors = [
                    c
                    for url, c in zip(settings.get("calendarURLs[]", []), calendar_colors)
                    if url.strip()
                ]

        if not calendar_urls:
            raise RuntimeError("At least one calendar URL is required")

        if not calendar_colors or len(calendar_colors) < len(calendar_urls):
            default_color = "#3788d8"
            calendar_colors = (calendar_colors or []) + [default_color] * (
                len(calendar_urls) - len(calendar_colors or [])
            )

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        timezone = device_config.get_config("timezone", default="America/New_York")
        time_format = device_config.get_config("time_format", default="12h")
        tz = pytz.timezone(timezone)
        current_dt = datetime.now(tz)

        start_dt, end_dt = self._get_week_range(current_dt, settings)
        events = self.fetch_ics_events(calendar_urls, calendar_colors, tz, start_dt, end_dt)
        return self._render_week_columns(
            dimensions, events, current_dt, time_format, settings, start_dt.date()
        )

    def _get_week_range(self, current_dt, settings):
        week_start_day = int(settings.get("weekStartDay", 1))
        # Existing setting format: 0=Sun..6=Sat. Python weekday: 0=Mon..6=Sun.
        python_week_start = (week_start_day - 1) % 7
        offset = (current_dt.weekday() - python_week_start) % 7
        start_dt = (current_dt - timedelta(days=offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_dt = start_dt + timedelta(days=7)
        return start_dt, end_dt

    def _format_time(self, dt, time_format):
        if time_format == "12h":
            return dt.strftime("%I:%M %p").lstrip("0")
        return dt.strftime("%H:%M")

    def _event_rows_for_week(self, events, week_start_date, show_time, time_format):
        days = [[] for _ in range(7)]

        for evt in events:
            try:
                start_raw = evt.get("start")
                if not start_raw:
                    continue

                all_day = bool(evt.get("allDay"))
                title = str(evt.get("title", "")).strip() or "(No title)"
                marker_color = evt.get("backgroundColor", "#000000")

                if all_day:
                    start_date = date.fromisoformat(start_raw)
                    end_raw = evt.get("end")
                    if end_raw:
                        end_date = date.fromisoformat(end_raw)
                    else:
                        end_date = start_date + timedelta(days=1)

                    span_days = max(1, (end_date - start_date).days)
                    for i in range(span_days):
                        day = start_date + timedelta(days=i)
                        idx = (day - week_start_date).days
                        if 0 <= idx < 7:
                            label = f"All day {title}"
                            days[idx].append((label, marker_color, day, datetime.min.time()))
                else:
                    start_dt = datetime.fromisoformat(start_raw)
                    end_raw = evt.get("end")
                    end_dt = datetime.fromisoformat(end_raw) if end_raw and "T" in end_raw else None
                    day = start_dt.date()
                    idx = (day - week_start_date).days
                    if 0 <= idx < 7:
                        if show_time:
                            if end_dt and end_dt.date() == start_dt.date():
                                time_prefix = (
                                    f"{self._format_time(start_dt, time_format)}-"
                                    f"{self._format_time(end_dt, time_format)}"
                                )
                            else:
                                time_prefix = self._format_time(start_dt, time_format)
                            label = f"{time_prefix} {title}"
                        else:
                            label = title
                        days[idx].append((label, marker_color, day, start_dt.time()))

            except (TypeError, ValueError):
                continue

        for i in range(7):
            days[i].sort(key=lambda row: (row[2], row[3], row[0]))
        return days

    def _render_week_columns(self, dimensions, events, current_dt, time_format, settings, week_start_date):
        width, height = dimensions
        bg_color = settings.get("backgroundColor", "#ffffff")
        text_color = self._readable_text_color(settings.get("textColor", "#000000"), bg_color)
        show_title = settings.get("displayTitle") == "true"
        show_time = settings.get("displayEventTime", "true") == "true"
        font_scale = FONT_SIZES.get(settings.get("fontSize", "normal"), 1)

        image = Image.new("RGBA", dimensions, bg_color)
        draw = ImageDraw.Draw(image)

        margin = int(width * 0.015)
        title_size = int(min(height * 0.05, width * 0.04) * font_scale)
        header_size = int(min(height * 0.028, width * 0.02) * font_scale)
        event_size = max(11, int(min(height * 0.023, width * 0.016) * font_scale))

        title_font = get_font("Jost", title_size, "bold")
        header_font = get_font("Jost", header_size, "bold")
        event_font = get_font("Jost", event_size)

        y = margin

        if show_title:
            week_end = week_start_date + timedelta(days=6)
            title = (
                f"{week_start_date.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
                if week_start_date.year == week_end.year
                else f"{week_start_date.strftime('%b %d, %Y')} - {week_end.strftime('%b %d, %Y')}"
            )
            tw = get_text_dimensions(draw, title, title_font)[0]
            draw.text(((width - tw) // 2, y), title, font=title_font, fill=text_color)
            y += get_text_dimensions(draw, title, title_font)[1] + int(height * 0.01)

        col_top = y
        col_h = height - margin - col_top
        col_w = max(1, (width - margin * 2) // 7)
        day_rows = self._event_rows_for_week(events, week_start_date, show_time, time_format)
        today = current_dt.date()

        for i in range(7):
            x0 = margin + i * col_w
            x1 = margin + (i + 1) * col_w if i < 6 else width - margin

            draw.rectangle((x0, col_top, x1, col_top + col_h), outline=text_color, width=1)

            day = week_start_date + timedelta(days=i)
            header = day.strftime("%a %d")
            header_w = get_text_dimensions(draw, header, header_font)[0]
            header_x = x0 + max(2, (x1 - x0 - header_w) // 2)
            draw.text((header_x, col_top + 4), header, font=header_font, fill=text_color)
            header_h = get_text_dimensions(draw, "Ag", header_font)[1]
            sep_y = col_top + header_h + 9
            draw.line((x0 + 2, sep_y, x1 - 2, sep_y), fill=text_color, width=1)

            if day == today:
                draw.rectangle((x0 + 1, col_top + 1, x1 - 1, col_top + col_h - 1), outline=text_color, width=2)

            row_y = sep_y + 4
            line_h = get_text_dimensions(draw, "Ag", event_font)[1] + 2
            usable_w = max(8, x1 - x0 - 10)
            bottom = col_top + col_h - 4
            rows = day_rows[i]
            row_idx = 0

            while row_idx < len(rows):
                label, marker_color, _, _ = rows[row_idx]
                wrapped_lines = self._wrap_text(draw, label, event_font, usable_w - 6)
                entry_h = max(line_h + 2, len(wrapped_lines) * line_h + 2)

                if row_y + entry_h > bottom:
                    remaining = len(rows) - row_idx
                    more_label = f"+{remaining} more"
                    if row_y + line_h <= bottom:
                        draw.text((x0 + 5, row_y), more_label, font=event_font, fill=text_color)
                    break

                draw.rectangle((x0 + 3, row_y + 2, x0 + 5, row_y + entry_h - 2), fill=marker_color)
                text_y = row_y + 1
                for line in wrapped_lines:
                    draw.text((x0 + 7, text_y), line, font=event_font, fill=text_color)
                    text_y += line_h

                row_y += entry_h + 1
                row_idx += 1

        return image
