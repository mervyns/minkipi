"""Weekly Calendar plugin — calendar renderer locked to weekly view."""

from plugins.calendar.calendar import Calendar


class WeeklyCalendar(Calendar):
    """Calendar variant that always renders in week mode."""

    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["settings_template"] = "weekly_calendar/settings.html"
        return template_params

    def generate_image(self, settings, device_config):
        weekly_settings = dict(settings or {})
        weekly_settings["viewMode"] = "timeGridWeek"
        return super().generate_image(weekly_settings, device_config)
